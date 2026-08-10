"""FastAPI application: REST API + local inspection web UI."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ragforge import __version__
from ragforge.api.jobs import Job, store
from ragforge.api.schemas import (
    ChunkPage,
    FormatsResponse,
    HealthResponse,
    JobResponse,
    JobSummary,
    PreviewResponse,
    ProcessOptions,
    ProcessTextRequest,
)
from ragforge.chunking.engine import available_strategies
from ragforge.errors import RagForgeError
from ragforge.exporters.base import available_formats, get_exporter
from ragforge.models.config import SizeUnit, Strategy
from ragforge.models.result import Statistics
from ragforge.parsers.base import get_parser, supported_extensions
from ragforge.pipeline import Pipeline
from ragforge.quality.validator import DatasetValidator

_STATIC_DIR = Path(__file__).parent / "static"
_MAX_UPLOAD_BYTES = 64 * 1024 * 1024

app = FastAPI(
    title="RAG ChunkForge",
    description="Intelligent document chunking for production RAG datasets.",
    version=__version__,
)


# ----------------------------------------------------------------------
# Meta
# ----------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(version=__version__, jobs=len(store))


@app.get("/formats", response_model=FormatsResponse, tags=["meta"])
def formats() -> FormatsResponse:
    return FormatsResponse(
        input_formats=supported_extensions(),
        output_formats=available_formats(),
        strategies=available_strategies(),
        units=[u.value for u in SizeUnit],
    )


# ----------------------------------------------------------------------
# Processing
# ----------------------------------------------------------------------
@app.post("/process", response_model=JobResponse, tags=["processing"])
async def process_upload(
    file: Annotated[UploadFile, File(description="Document to chunk.")],
    strategy: Annotated[str, Form()] = Strategy.SEMANTIC.value,
    target_size: Annotated[int, Form()] = 500,
    min_size: Annotated[int, Form()] = 100,
    max_size: Annotated[int, Form()] = 800,
    overlap: Annotated[float, Form()] = 75,
    unit: Annotated[str, Form()] = SizeUnit.TOKENS.value,
    clean: Annotated[bool, Form()] = True,
    deduplicate: Annotated[bool, Form()] = True,
    context_prefix: Annotated[bool, Form()] = True,
    separate_retrieval_metadata: Annotated[bool, Form()] = True,
) -> JobResponse:
    """Upload a document and receive a completed chunking job."""
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (limit 64 MB).")
    filename = file.filename or "document.txt"

    try:
        options = ProcessOptions(
            strategy=Strategy(strategy),
            target_size=target_size,
            min_size=min_size,
            max_size=max_size,
            overlap=overlap,
            unit=SizeUnit(unit),
            clean=clean,
            deduplicate=deduplicate,
            context_prefix=context_prefix,
            separate_retrieval_metadata=separate_retrieval_metadata,
        )
        config = options.to_config()
    except (ValueError, RagForgeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = store.create(title=filename, source=filename)
    suffix = Path(filename).suffix.lower() or ".txt"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(raw)
            tmp_path = Path(handle.name)
        get_parser(Path(filename))  # early, friendly unsupported-format error
        pipeline = Pipeline(config)
        document, chunks = pipeline.process_file(tmp_path)
        document = document.model_copy(
            update={"source": filename, "title": _title(document, filename)}
        )
        for chunk in chunks:
            chunk.metadata.source = filename
            chunk.metadata.title = document.title
        _finish(job, pipeline, [document], chunks, config)
    except RagForgeError as exc:
        job.status = "failed"
        job.error = str(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected
        job.status = "failed"
        job.error = str(exc)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return _job_response(job)


@app.post("/process/text", response_model=JobResponse, tags=["processing"])
def process_text(request: ProcessTextRequest) -> JobResponse:
    """Chunk raw text supplied as JSON."""
    try:
        config = request.options.to_config()
    except RagForgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = store.create(title=request.title, source=request.source)
    try:
        pipeline = Pipeline(config)
        document, chunks = pipeline.process_text(
            request.text, title=request.title, source=request.source
        )
        _finish(job, pipeline, [document], chunks, config)
    except RagForgeError as exc:
        job.status = "failed"
        job.error = str(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(job)


# ----------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------
@app.get("/jobs", response_model=list[JobSummary], tags=["jobs"])
def list_jobs() -> list[JobSummary]:
    return [_summary(job) for job in store.list()]


@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
def get_job(job_id: str) -> JobResponse:
    return _job_response(_require(job_id))


@app.delete("/jobs/{job_id}", tags=["jobs"])
def delete_job(job_id: str) -> dict[str, str]:
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"status": "deleted", "job_id": job_id}


@app.get("/jobs/{job_id}/chunks", response_model=ChunkPage, tags=["jobs"])
def get_chunks(
    job_id: str,
    search: Annotated[str | None, Query(description="Case-insensitive content filter.")] = None,
    section: Annotated[str | None, Query(description="Heading path filter.")] = None,
    content_type: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query(description="Filter by semantic role.")] = None,
    knowledge_only: Annotated[
        bool, Query(description="Exclude metadata and navigation chunks.")
    ] = False,
    flagged: Annotated[bool, Query(description="Only chunks with quality flags.")] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ChunkPage:
    job = _require(job_id)
    chunks = job.chunks
    if search:
        needle = search.casefold()
        chunks = [c for c in chunks if needle in c.content.casefold()]
    if section:
        needle = section.casefold()
        chunks = [c for c in chunks if needle in " > ".join(c.metadata.heading_path).casefold()]
    if content_type:
        chunks = [c for c in chunks if c.metadata.content_type == content_type]
    if role:
        chunks = [c for c in chunks if c.metadata.semantic_role == role]
    if knowledge_only:
        chunks = [c for c in chunks if c.is_knowledge]
    if flagged:
        chunks = [c for c in chunks if c.quality and c.quality.flags]
    return ChunkPage(
        job_id=job_id,
        total=len(chunks),
        offset=offset,
        limit=limit,
        chunks=chunks[offset : offset + limit],
    )


@app.get("/jobs/{job_id}/statistics", response_model=Statistics, tags=["jobs"])
def get_statistics(job_id: str) -> Statistics:
    job = _require(job_id)
    return job.statistics or Statistics()


@app.get("/jobs/{job_id}/validate", tags=["jobs"])
def validate_job(job_id: str) -> dict[str, Any]:
    job = _require(job_id)
    report = DatasetValidator().validate(job.chunks)
    return {
        "ok": report.ok,
        "checked": report.checked,
        "errors": [i.to_dict() for i in report.errors],
        "warnings": [i.to_dict() for i in report.warnings],
        "summary": report.summary(),
        "coverage": job.statistics.coverage if job.statistics else {},
    }


@app.get("/jobs/{job_id}/preview", response_model=PreviewResponse, tags=["jobs"])
def get_preview(job_id: str) -> PreviewResponse:
    """Original document text plus chunk boundary spans for highlighting."""
    job = _require(job_id)
    documents: list[dict[str, Any]] = []
    for document in job.documents:
        spans = [
            {
                "chunk_id": c.id,
                "chunk_index": c.metadata.chunk_index,
                "start": c.metadata.start_offset,
                "end": c.metadata.end_offset,
                "section": c.metadata.section,
                "content_type": c.metadata.content_type,
            }
            for c in job.chunks
            if c.metadata.document_id == document.id
        ]
        documents.append(
            {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "content": document.content,
                "spans": spans,
            }
        )
    return PreviewResponse(job_id=job_id, documents=documents)


@app.get("/jobs/{job_id}/export", tags=["jobs"])
def export_job(
    job_id: str,
    format: Annotated[str, Query(description="jsonl | json | csv | markdown")] = "jsonl",
) -> Any:
    job = _require(job_id)
    try:
        exporter = get_exporter(format)
    except RagForgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"chunks{exporter.extension}"
        exporter.write(job.chunks, path)
        data = path.read_bytes()
    media = {
        "jsonl": "application/x-ndjson",
        "json": "application/json",
        "csv": "text/csv",
        "markdown": "text/markdown",
    }.get(format, "application/octet-stream")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="chunks{exporter.extension}"'},
    )


# ----------------------------------------------------------------------
# Web UI
# ----------------------------------------------------------------------
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> Any:
    index_file = _STATIC_DIR / "index.html"
    if not index_file.is_file():  # pragma: no cover
        return HTMLResponse("<h1>RAG ChunkForge</h1><p>UI assets missing.</p>", status_code=200)
    return FileResponse(index_file)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _require(job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


def _finish(job: Job, pipeline: Pipeline, documents: list, chunks: list, config) -> None:
    chunks = pipeline.finalize(chunks)
    job.chunks = chunks
    job.documents = documents
    job.statistics = Statistics.from_chunks(
        chunks,
        reports=[],
        project=config.project.name,
        strategy=config.chunking.strategy_name,
        unit=config.chunking.unit.value,
    )
    job.statistics.documents = len(documents)
    job.statistics.original_characters = sum(len(d.content) for d in documents)
    job.statistics.original_tokens = sum(pipeline.engine.meter.tokens(d.content) for d in documents)
    job.statistics.coverage = pipeline.aggregate_coverage()
    job.status = "completed"


def _title(document, filename: str) -> str:
    return document.title or Path(filename).stem


def _summary(job: Job) -> JobSummary:
    return JobSummary(
        job_id=job.id,
        status=job.status,
        chunks=job.chunk_count,
        documents=len(job.documents),
        created_at=job.created_at,
        title=job.title,
        source=job.source,
        error=job.error,
    )


def _job_response(job: Job) -> JobResponse:
    return JobResponse(**_summary(job).model_dump(), statistics=job.statistics)


__all__ = ["app"]
