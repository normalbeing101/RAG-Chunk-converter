"""In-memory job store for the API.

Jobs are ephemeral by design: the API is an inspection and integration surface,
not a database. A bounded LRU keeps memory usage predictable.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from ragforge.models.chunk import Chunk
from ragforge.models.document import Document
from ragforge.models.result import Statistics


@dataclass(slots=True)
class Job:
    """A completed (or failed) processing run."""

    id: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    title: str = ""
    source: str = ""
    chunks: list[Chunk] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    statistics: Statistics | None = None
    error: str | None = None

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


class JobStore:
    """Thread-safe bounded job registry."""

    def __init__(self, max_jobs: int = 50) -> None:
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self.max_jobs = max_jobs

    def create(self, *, title: str = "", source: str = "") -> Job:
        job = Job(id=uuid.uuid4().hex[:12], title=title, source=source, status="running")
        with self._lock:
            self._jobs[job.id] = job
            while len(self._jobs) > self.max_jobs:
                self._jobs.popitem(last=False)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._jobs.move_to_end(job_id)
            return job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)


store = JobStore()
