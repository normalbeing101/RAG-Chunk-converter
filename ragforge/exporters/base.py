"""Exporter interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from ragforge.errors import ExportError
from ragforge.models.chunk import Chunk
from ragforge.models.config import OutputConfig


class Exporter(ABC):
    """Writes chunks to a file in a specific format."""

    name: ClassVar[str] = "base"
    extension: ClassVar[str] = ".txt"

    def __init__(self, config: OutputConfig | None = None) -> None:
        self.config = config or OutputConfig()

    @abstractmethod
    def write(self, chunks: Iterable[Chunk], path: Path) -> Path:
        """Write ``chunks`` to ``path`` and return the resolved path."""

    def prepare(self, path: Path) -> Path:
        path = Path(path)
        if path.exists() and not self.config.overwrite:
            raise ExportError(
                f"Output file already exists: {path}",
                hint="Enable output.overwrite or choose a different filename.",
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportError(f"Cannot create output directory {path.parent}: {exc}") from exc
        return path


_REGISTRY: dict[str, type[Exporter]] = {}


def register_exporter(exporter: type[Exporter]) -> type[Exporter]:
    _REGISTRY[exporter.name] = exporter
    return exporter


def get_exporter(name: str, config: OutputConfig | None = None) -> Exporter:
    exporter_cls = _REGISTRY.get(name)
    if exporter_cls is None:
        raise ExportError(
            f"Unknown output format: {name}",
            hint=f"Available formats: {', '.join(sorted(_REGISTRY))}",
        )
    return exporter_cls(config)


def available_formats() -> list[str]:
    return sorted(_REGISTRY)
