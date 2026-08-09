"""JSONL and JSON exporters."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from ragforge.errors import ExportError
from ragforge.exporters.base import Exporter, register_exporter
from ragforge.models.chunk import Chunk


@register_exporter
class JsonlExporter(Exporter):
    """One JSON object per line - streams without buffering the whole dataset."""

    name: ClassVar[str] = "jsonl"
    extension: ClassVar[str] = ".jsonl"

    def write(self, chunks: Iterable[Chunk], path: Path) -> Path:
        path = self.prepare(path)
        include_quality = self.config.include_quality
        try:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                for chunk in chunks:
                    record = chunk.to_record(include_quality=include_quality)
                    handle.write(json.dumps(record, ensure_ascii=False))
                    handle.write("\n")
        except OSError as exc:
            raise ExportError(f"Failed to write {path}: {exc}") from exc
        return path


@register_exporter
class JsonExporter(Exporter):
    """Single JSON document with a ``documents`` array."""

    name: ClassVar[str] = "json"
    extension: ClassVar[str] = ".json"

    def write(self, chunks: Iterable[Chunk], path: Path) -> Path:
        path = self.prepare(path)
        include_quality = self.config.include_quality
        payload = {
            "documents": [chunk.to_record(include_quality=include_quality) for chunk in chunks]
        }
        try:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    indent=2 if self.config.pretty else None,
                )
                handle.write("\n")
        except OSError as exc:
            raise ExportError(f"Failed to write {path}: {exc}") from exc
        return path
