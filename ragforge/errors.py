"""Exception hierarchy.

Every user-facing failure raises a :class:`RagForgeError` subclass carrying a
short, actionable message. The CLI renders those messages without a traceback
unless ``--debug`` is passed.
"""

from __future__ import annotations


class RagForgeError(Exception):
    """Base class for all RAG ChunkForge errors."""

    hint: str | None = None

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if hint is not None:
            self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ConfigError(RagForgeError):
    """Raised when a configuration value is invalid or unreadable."""


class UnsupportedFormatError(RagForgeError):
    """Raised when no parser can handle a given file."""

    def __init__(self, suffix: str, supported: list[str] | None = None) -> None:
        supported_txt = ", ".join(sorted(supported or []))
        message = f"Unsupported file format: {suffix or '(no extension)'}"
        hint = f"Supported formats: {supported_txt}" if supported_txt else None
        super().__init__(message, hint=hint)
        self.suffix = suffix


class ParseError(RagForgeError):
    """Raised when a document cannot be parsed."""

    def __init__(self, source: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"Unable to parse {source}: {reason}", hint=hint)
        self.source = source
        self.reason = reason


class MissingDependencyError(RagForgeError):
    """Raised when an optional dependency is required but not installed."""

    def __init__(self, package: str, feature: str, extra: str | None = None) -> None:
        install = f"pip install {extra or package}"
        super().__init__(
            f"The '{feature}' feature requires the optional dependency '{package}'.",
            hint=f"Install it with: {install}",
        )
        self.package = package


class ChunkingError(RagForgeError):
    """Raised when the chunking engine cannot produce a valid result."""


class ExportError(RagForgeError):
    """Raised when writing an output dataset fails."""


class EmbeddingError(RagForgeError):
    """Raised when an embedding provider fails."""


class InputError(RagForgeError):
    """Raised for missing/invalid input paths."""
