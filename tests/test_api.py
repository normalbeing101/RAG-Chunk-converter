"""REST API tests."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ragforge.api.app import app
from ragforge.api.jobs import store


@pytest.fixture
def client():
    store.clear()
    with TestClient(app) as test_client:
        yield test_client
    store.clear()


@pytest.fixture
def job(client, markdown_doc):
    response = client.post(
        "/process",
        files={"file": ("guide.md", markdown_doc.encode("utf-8"), "text/markdown")},
        data={"target_size": "80", "min_size": "10", "max_size": "200", "overlap": "10"},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- meta
def test_health(client):
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert payload["version"]


def test_formats(client):
    payload = client.get("/formats").json()
    assert ".md" in payload["input_formats"]
    assert "jsonl" in payload["output_formats"]
    assert "recursive" in payload["strategies"]
    assert "tokens" in payload["units"]


def test_index_serves_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "RAG ChunkForge" in response.text


def test_static_assets(client):
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    assert "/process" in schema["paths"]
    assert "/jobs/{job_id}/chunks" in schema["paths"]


# ---------------------------------------------------------------- process
def test_process_upload(job):
    assert job["status"] == "completed"
    assert job["chunks"] > 0
    assert job["job_id"]
    assert job["statistics"]["total_chunks"] == job["chunks"]


def test_process_text_endpoint(client, markdown_doc):
    response = client.post(
        "/process/text",
        json={
            "text": markdown_doc,
            "title": "Inline",
            "options": {"target_size": 100, "min_size": 10, "max_size": 250, "overlap": 10},
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["chunks"] > 0
    assert payload["title"] == "Inline"


def test_process_rejects_empty_text(client):
    assert client.post("/process/text", json={"text": ""}).status_code == 422


def test_process_invalid_options(client, markdown_doc):
    response = client.post(
        "/process/text",
        json={
            "text": markdown_doc,
            "options": {"min_size": 900, "max_size": 100, "target_size": 500},
        },
    )
    assert response.status_code == 400
    assert "maximum must be greater than minimum" in response.json()["detail"]


def test_process_unsupported_format(client):
    response = client.post(
        "/process", files={"file": ("thing.xyz", b"data", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_process_malformed_json_upload(client):
    response = client.post(
        "/process", files={"file": ("bad.json", b"{not json", "application/json")}
    )
    assert response.status_code == 400
    assert "Unable to parse" in response.json()["detail"]


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("a.txt", b"Plain text content that is long enough to chunk into something useful."),
        ("a.html", b"<h1>Title</h1><p>Paragraph content here for chunking.</p>"),
        ("a.csv", b"name,role\nAda,engineer\nGrace,admiral\n"),
        ("a.json", b'[{"title":"A","body":"first"},{"title":"B","body":"second"}]'),
    ],
)
def test_process_various_formats(client, name, payload):
    response = client.post("/process", files={"file": (name, payload, "text/plain")})
    assert response.status_code == 200, response.text
    assert response.json()["chunks"] > 0


# ---------------------------------------------------------------- jobs
def test_get_job(client, job):
    payload = client.get(f"/jobs/{job['job_id']}").json()
    assert payload["job_id"] == job["job_id"]
    assert payload["status"] == "completed"


def test_job_not_found(client):
    response = client.get("/jobs/doesnotexist")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


def test_list_jobs(client, job):
    jobs = client.get("/jobs").json()
    assert any(j["job_id"] == job["job_id"] for j in jobs)


def test_delete_job(client, job):
    assert client.delete(f"/jobs/{job['job_id']}").status_code == 200
    assert client.get(f"/jobs/{job['job_id']}").status_code == 404
    assert client.delete(f"/jobs/{job['job_id']}").status_code == 404


# ---------------------------------------------------------------- chunks
def test_get_chunks(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/chunks").json()
    assert payload["total"] == job["chunks"]
    first = payload["chunks"][0]
    assert first["id"]
    assert first["metadata"]["heading_path"]
    assert first["quality"]["quality_score"] >= 0


def test_chunk_pagination(client, job):
    page = client.get(f"/jobs/{job['job_id']}/chunks?limit=2&offset=1").json()
    assert len(page["chunks"]) <= 2
    assert page["offset"] == 1


def test_chunk_search_filter(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/chunks?search=sub-events").json()
    assert payload["total"] >= 1
    assert all("sub-events" in c["content"].lower() for c in payload["chunks"])


def test_chunk_section_filter(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/chunks?section=Example").json()
    assert payload["total"] >= 1


def test_chunk_content_type_filter(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/chunks?content_type=code").json()
    assert all(c["metadata"]["content_type"] == "code" for c in payload["chunks"])


def test_chunk_flagged_filter(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/chunks?flagged=true").json()
    assert all(c["quality"]["flags"] for c in payload["chunks"])


# ---------------------------------------------------------------- other
def test_statistics(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/statistics").json()
    assert payload["total_chunks"] == job["chunks"]
    assert payload["size_histogram"]
    assert payload["chunks_by_section"]


def test_validate_endpoint(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/validate").json()
    assert payload["ok"] is True
    assert payload["checked"] == job["chunks"]


def test_preview_spans(client, job):
    payload = client.get(f"/jobs/{job['job_id']}/preview").json()
    assert len(payload["documents"]) == 1
    document = payload["documents"][0]
    assert document["content"]
    assert document["spans"]
    for span in document["spans"]:
        assert span["end"] >= span["start"]
        assert span["chunk_id"]


@pytest.mark.parametrize("fmt", ["jsonl", "json", "csv", "markdown"])
def test_export_formats(client, job, fmt):
    response = client.get(f"/jobs/{job['job_id']}/export?format={fmt}")
    assert response.status_code == 200
    assert response.content
    assert "attachment" in response.headers["content-disposition"]
    if fmt == "jsonl":
        first = response.text.strip().split("\n")[0]
        assert json.loads(first)["id"]


def test_export_invalid_format(client, job):
    response = client.get(f"/jobs/{job['job_id']}/export?format=xml")
    assert response.status_code == 400


def test_job_store_is_bounded():
    from ragforge.api.jobs import JobStore

    small = JobStore(max_jobs=3)
    ids = [small.create().id for _ in range(5)]
    assert len(small) == 3
    assert small.get(ids[0]) is None
    assert small.get(ids[-1]) is not None
