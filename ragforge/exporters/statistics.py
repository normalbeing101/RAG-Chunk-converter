"""Statistics writer."""

from __future__ import annotations

import json
from pathlib import Path

from ragforge.errors import ExportError
from ragforge.models.result import Statistics


def write_statistics(statistics: Statistics, path: Path) -> Path:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(statistics.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        raise ExportError(f"Failed to write statistics to {path}: {exc}") from exc
    return path
