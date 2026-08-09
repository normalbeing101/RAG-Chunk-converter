"""Progress reporting abstraction.

The pipeline never imports Rich directly; it emits progress events through a
:class:`ProgressReporter`. The CLI supplies a Rich-backed implementation, while
library users get a no-op reporter by default.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class ProgressReporter(Protocol):
    """Receives progress updates from the pipeline."""

    def start(self, total: int, description: str) -> None: ...

    def advance(self, amount: int = 1, *, detail: str | None = None) -> None: ...

    def finish(self) -> None: ...


class NullProgress:
    """Default reporter that discards all events."""

    def start(self, total: int, description: str) -> None:
        return None

    def advance(self, amount: int = 1, *, detail: str | None = None) -> None:
        return None

    def finish(self) -> None:
        return None


class CallbackProgress:
    """Adapter that forwards progress to a simple callable."""

    def __init__(self, callback) -> None:
        self._callback = callback
        self._total = 0
        self._done = 0

    def start(self, total: int, description: str) -> None:
        self._total = total
        self._done = 0
        self._callback(0, total, description)

    def advance(self, amount: int = 1, *, detail: str | None = None) -> None:
        self._done += amount
        self._callback(self._done, self._total, detail or "")

    def finish(self) -> None:
        self._callback(self._total, self._total, "done")


@contextmanager
def progress_scope(reporter: ProgressReporter, total: int, description: str) -> Iterator[None]:
    reporter.start(total, description)
    try:
        yield
    finally:
        reporter.finish()
