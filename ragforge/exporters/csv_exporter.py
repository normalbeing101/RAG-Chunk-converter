"""CSV exporter."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from ragforge.errors import ExportError
from ragforge.exporters.base import Exporter, register_exporter
from ragforge.models.chunk import Chunk

_COLUMNS = [
    "id",
    "document_id",
    "content",
    "title",
    "section",
    "source",
    "chunk_index",
    "content_type",
    "semantic_role",
    "keywords",
]


@register_exporter
class CsvExporter(Exporter):
    name: ClassVar[str] = "csv"
    extension: ClassVar[str] = ".csv"

    def write(self, chunks: Iterable[Chunk], path: Path) -> Path:
        path = self.prepare(path)
        try:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=_COLUMNS, extrasaction="ignore")
                writer.writeheader()
                for chunk in chunks:
                    writer.writerow(chunk.flat_record())
        except OSError as exc:
            raise ExportError(f"Failed to write {path}: {exc}") from exc
        return path
