/* RAG ChunkForge - local inspection UI (no build step, no dependencies). */
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  jobId: null,
  chunks: [],
  filtered: [],
  statistics: null,
  preview: null,
  selected: null,
  inputMode: "file",
};

/* ------------------------------------------------------------------ init */
document.addEventListener("DOMContentLoaded", () => {
  bindInputTabs();
  bindMainTabs();
  bindSliders();
  bindDropzone();
  bindFilters();
  bindExport();
  $("run").addEventListener("click", run);
  loadMeta();
});

async function loadMeta() {
  try {
    const [health, formats] = await Promise.all([
      fetch("/health").then((r) => r.json()),
      fetch("/formats").then((r) => r.json()),
    ]);
    $("version").textContent = "v" + health.version;
    $("accepted").textContent = formats.input_formats.join("  ");
    const select = $("strategy");
    const known = new Set([...select.options].map((o) => o.value));
    formats.strategies.forEach((s) => {
      if (!known.has(s)) select.add(new Option(s, s));
    });
  } catch (_) {
    /* offline-friendly */
  }
}

/* ------------------------------------------------------------------ ui */
function bindInputTabs() {
  document.querySelectorAll("[data-input]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("[data-input]").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.inputMode = tab.dataset.input;
      $("input-file").classList.toggle("hidden", state.inputMode !== "file");
      $("input-text").classList.toggle("hidden", state.inputMode !== "text");
    });
  });
}

function bindMainTabs() {
  document.querySelectorAll("[data-view]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("[data-view]").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      ["chunks", "preview", "charts", "export"].forEach((view) => {
        $("view-" + view).classList.toggle("hidden", view !== tab.dataset.view);
      });
      if (tab.dataset.view === "preview") renderPreview();
    });
  });
}

function bindSliders() {
  const sync = (id, out) => {
    const el = $(id);
    const update = () => ($(out).textContent = el.value);
    el.addEventListener("input", update);
    update();
  };
  sync("target-size", "target-size-out");
  sync("overlap", "overlap-out");
  $("unit").addEventListener("change", () => {
    const unit = $("unit").value;
    const scale = unit === "characters" ? 8 : 1;
    $("target-size").max = 2000 * scale;
    $("overlap").max = 400 * scale;
    $("target-size").value = 500 * scale;
    $("overlap").value = 75 * scale;
    $("min-size").value = 100 * scale;
    $("max-size").value = 800 * scale;
    $("target-size-out").textContent = $("target-size").value;
    $("overlap-out").textContent = $("overlap").value;
  });
}

function bindDropzone() {
  const zone = $("dropzone");
  const input = $("file");
  input.addEventListener("change", () => {
    if (input.files.length) $("filename").textContent = input.files[0].name;
  });
  ["dragenter", "dragover"].forEach((evt) =>
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.add("dragging");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.remove("dragging");
    })
  );
  zone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      $("filename").textContent = e.dataTransfer.files[0].name;
    }
  });
}

function bindFilters() {
  let timer = null;
  const apply = () => {
    clearTimeout(timer);
    timer = setTimeout(filterChunks, 120);
  };
  $("search").addEventListener("input", apply);
  $("filter-type").addEventListener("change", filterChunks);
  $("filter-flagged").addEventListener("change", filterChunks);
}

function bindExport() {
  document.querySelectorAll("[data-export]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!state.jobId) return;
      window.location.href = `/jobs/${state.jobId}/export?format=${button.dataset.export}`;
    });
  });
  $("validate").addEventListener("click", async () => {
    if (!state.jobId) return;
    const report = await fetch(`/jobs/${state.jobId}/validate`).then((r) => r.json());
    $("validation").textContent = JSON.stringify(report, null, 2);
  });
}

/* ------------------------------------------------------------------ run */
function options() {
  return {
    strategy: $("strategy").value,
    target_size: Number($("target-size").value),
    min_size: Number($("min-size").value),
    max_size: Number($("max-size").value),
    overlap: Number($("overlap").value),
    unit: $("unit").value,
    clean: $("clean").checked,
    deduplicate: $("dedup").checked,
    context_prefix: $("prefix").checked,
  };
}

async function run() {
  const button = $("run");
  setStatus("Processing...", "busy");
  button.disabled = true;
  try {
    const job = state.inputMode === "file" ? await runFile() : await runText();
    state.jobId = job.job_id;
    state.statistics = job.statistics;
    await loadChunks();
    state.preview = null;
    $("empty").classList.add("hidden");
    $("results").classList.remove("hidden");
    renderStatistics();
    renderCharts();
    setStatus(`Done - ${job.chunks} chunks`, "ok");
  } catch (error) {
    setStatus(error.message || String(error), "error");
  } finally {
    button.disabled = false;
  }
}

async function runFile() {
  const input = $("file");
  if (!input.files.length) throw new Error("Choose a file first.");
  const form = new FormData();
  form.append("file", input.files[0]);
  Object.entries(options()).forEach(([key, value]) => form.append(key, value));
  return request("/process", { method: "POST", body: form });
}

async function runText() {
  const text = $("text").value.trim();
  if (!text) throw new Error("Paste some text first.");
  return request("/process/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, title: $("text-title").value || "Pasted document", options: options() }),
  });
}

async function request(url, init) {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

async function loadChunks() {
  const page = await request(`/jobs/${state.jobId}/chunks?limit=500`);
  state.chunks = page.chunks;
  const types = [...new Set(state.chunks.map((c) => c.metadata.content_type))].sort();
  const select = $("filter-type");
  select.innerHTML = '<option value="">All types</option>';
  types.forEach((t) => select.add(new Option(t, t)));
  filterChunks();
}

/* ------------------------------------------------------------------ render */
function setStatus(message, kind) {
  const el = $("status");
  el.textContent = message;
  el.className = "status " + (kind || "");
}

function renderStatistics() {
  const s = state.statistics || {};
  const set = (id, value) => ($(id).textContent = value);
  set("s-documents", fmt(s.documents));
  set("s-tokens", fmt(s.original_tokens));
  set("s-chunks", fmt(s.total_chunks));
  set("s-avg", Math.round(s.average_size || 0));
  set("s-median", Math.round(s.median_size || 0));
  set("s-dupes", fmt(s.duplicates));
  set("s-warnings", fmt(s.warnings));
  set("s-quality", (s.average_quality || 0).toFixed(2));
}

function filterChunks() {
  const needle = $("search").value.trim().toLowerCase();
  const type = $("filter-type").value;
  const flagged = $("filter-flagged").checked;
  state.filtered = state.chunks.filter((c) => {
    if (needle && !c.content.toLowerCase().includes(needle)) return false;
    if (type && c.metadata.content_type !== type) return false;
    if (flagged && !(c.quality && c.quality.flags.length)) return false;
    return true;
  });
  $("chunk-count").textContent = `${state.filtered.length} / ${state.chunks.length} chunks`;
  renderChunkList();
}

function renderChunkList() {
  const list = $("chunk-list");
  list.innerHTML = "";
  if (!state.filtered.length) {
    list.innerHTML = '<p class="muted">No chunks match the current filters.</p>';
    return;
  }
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((chunk) => {
    const flags = (chunk.quality && chunk.quality.flags) || [];
    const item = document.createElement("div");
    item.className = "chunk-item" + (flags.length ? " flagged" : "");
    item.dataset.id = chunk.id;
    item.innerHTML = `
      <div class="head">
        <span>#${chunk.metadata.chunk_index} &middot; ${escapeHtml(chunk.metadata.content_type)}</span>
        <span>${chunk.metadata.size} ${escapeHtml(chunk.metadata.unit)} &middot; Q ${
      chunk.quality ? chunk.quality.quality_score.toFixed(2) : "-"
    }</span>
      </div>
      <div class="path">${escapeHtml(chunk.metadata.heading_path.join(" > ") || "(no section)")}</div>
      <div class="snippet">${escapeHtml(chunk.content.slice(0, 220))}</div>`;
    item.addEventListener("click", () => selectChunk(chunk.id));
    fragment.appendChild(item);
  });
  list.appendChild(fragment);
  if (state.selected && state.filtered.some((c) => c.id === state.selected)) {
    highlightSelection();
  }
}

function selectChunk(id) {
  state.selected = id;
  highlightSelection();
  const chunk = state.chunks.find((c) => c.id === id);
  if (!chunk) return;
  const m = chunk.metadata;
  const flags = (chunk.quality && chunk.quality.flags) || [];
  const rows = [
    ["id", chunk.id],
    ["document", `${m.title || ""} (${m.document_id})`],
    ["source", m.source || "-"],
    ["heading path", m.heading_path.join(" > ") || "-"],
    ["section", m.section || "-"],
    ["parent section", m.parent_section || "-"],
    ["content type", m.content_type + (m.language ? ` / ${m.language}` : "")],
    ["index", `${m.chunk_index + 1} / ${m.total_chunks}`],
    ["size", `${m.size} ${m.unit}`],
    ["characters / words / tokens", `${m.char_count} / ${m.word_count} / ${m.token_count}`],
    ["sentences", m.sentence_count],
    ["offsets", `${m.start_offset} - ${m.end_offset}`],
    ["overlap chars", m.overlap_prefix_chars],
    ["parent id", m.parent_id || "-"],
    ["previous", m.previous_chunk || "-"],
    ["next", m.next_chunk || "-"],
  ];
  if (m.duplicate_of) rows.push(["duplicate of", `${m.duplicate_of} (${m.similarity})`]);
  if (chunk.quality) {
    rows.push([
      "quality",
      `${chunk.quality.quality_score.toFixed(2)} (len ${chunk.quality.length_score.toFixed(2)}, ` +
        `coh ${chunk.quality.coherence_score.toFixed(2)}, ctx ${chunk.quality.context_score.toFixed(2)}, ` +
        `info ${chunk.quality.information_score.toFixed(2)})`,
    ]);
  }

  const badges = flags.length
    ? flags.map((f) => `<span class="badge flag">${escapeHtml(f)}</span>`).join("")
    : '<span class="badge good">no warnings</span>';

  $("chunk-detail").innerHTML = `
    <h3>${escapeHtml(chunk.id)}</h3>
    <div>${badges}</div>
    ${chunk.context_prefix ? `<h3 style="margin-top:1rem">Context prefix</h3><pre>${escapeHtml(chunk.context_prefix)}</pre>` : ""}
    <h3>Content</h3>
    <pre>${escapeHtml(chunk.content)}</pre>
    <h3>Metadata</h3>
    <table class="meta-table">${rows
      .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(String(v))}</td></tr>`)
      .join("")}</table>`;
  $("chunk-detail").scrollTop = 0;
}

function highlightSelection() {
  document.querySelectorAll(".chunk-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.id === state.selected);
  });
}

/* ------------------------------------------------------------------ preview */
async function renderPreview() {
  if (!state.jobId) return;
  if (!state.preview) {
    state.preview = await request(`/jobs/${state.jobId}/preview`);
  }
  const container = $("preview");
  container.innerHTML = "";
  state.preview.documents.forEach((doc) => {
    const spans = [...doc.spans].sort((a, b) => a.start - b.start);
    const wrapper = document.createElement("div");
    let cursor = 0;
    let index = 0;
    spans.forEach((span) => {
      const start = Math.max(span.start, cursor);
      const end = Math.max(span.end, start);
      if (start > cursor) {
        wrapper.appendChild(document.createTextNode(doc.content.slice(cursor, start)));
      }
      const piece = doc.content.slice(start, end);
      if (piece) {
        const node = document.createElement("span");
        node.className = "seg " + (index % 2 ? "b" : "a");
        node.title = `${span.chunk_id}\n${span.section || "(no section)"} [${span.content_type}]`;
        node.textContent = piece;
        node.addEventListener("click", () => {
          state.selected = span.chunk_id;
          document.querySelector('[data-view="chunks"]').click();
          selectChunk(span.chunk_id);
        });
        wrapper.appendChild(node);
        index += 1;
      }
      cursor = Math.max(cursor, end);
    });
    if (cursor < doc.content.length) {
      wrapper.appendChild(document.createTextNode(doc.content.slice(cursor)));
    }
    container.appendChild(wrapper);
  });
}

/* ------------------------------------------------------------------ charts */
function renderCharts() {
  const s = state.statistics || {};
  const histogram = (s.size_histogram || []).map((b) => [
    `${Math.round(b.start)}-${Math.round(b.end)}`,
    b.count,
  ]);
  bars("histogram", histogram);
  bars("by-document", entries(s.chunks_by_document));
  bars("by-type", entries(s.chunks_by_content_type));
  bars("by-section", entries(s.chunks_by_section, 20));
  bars("by-flag", entries(s.flag_counts));
}

function entries(object, limit = 12) {
  return Object.entries(object || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function bars(id, data) {
  const target = $(id);
  if (!data.length) {
    target.innerHTML = '<p class="muted">No data.</p>';
    return;
  }
  const peak = Math.max(...data.map((d) => d[1])) || 1;
  target.innerHTML = data
    .map(
      ([label, value]) => `
      <div class="bar-row">
        <span class="label" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        <span class="track"><span class="fill" style="width:${(value / peak) * 100}%"></span></span>
        <span class="value">${fmt(value)}</span>
      </div>`
    )
    .join("");
}

/* ------------------------------------------------------------------ utils */
function fmt(value) {
  return (value || 0).toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
