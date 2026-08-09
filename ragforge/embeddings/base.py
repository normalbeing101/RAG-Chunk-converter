"""Embedding provider abstraction.

The chunking pipeline is fully functional without embeddings. Providers are
resolved lazily so that optional heavy dependencies are only imported when a
provider is actually used.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import ClassVar

from ragforge.errors import EmbeddingError
from ragforge.models.chunk import Chunk
from ragforge.models.config import EmbeddingConfig


class EmbeddingProvider(ABC):
    """Minimal interface every provider must implement."""

    name: ClassVar[str] = "base"

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    @property
    def dimensions(self) -> int:
        return self.config.dimensions

    def embed_chunks(self, chunks: Iterable[Chunk]) -> list[Chunk]:
        """Attach embeddings to chunks in batches."""
        items = list(chunks)
        if not items:
            return items
        batch_size = max(1, self.config.batch_size)
        use_prefix = self.config.embed_context_prefix
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            texts = [c.text_for_embedding if use_prefix else c.content for c in batch]
            vectors = self.embed(texts)
            if len(vectors) != len(batch):
                raise EmbeddingError(
                    f"Provider '{self.name}' returned {len(vectors)} vectors "
                    f"for {len(batch)} inputs."
                )
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = list(vector)
        return items


_REGISTRY: dict[str, type[EmbeddingProvider]] = {}


def register_provider(provider: type[EmbeddingProvider]) -> type[EmbeddingProvider]:
    _REGISTRY[provider.name] = provider
    return provider


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def get_provider(config: EmbeddingConfig | None = None) -> EmbeddingProvider:
    cfg = config or EmbeddingConfig()
    provider_cls = _REGISTRY.get(cfg.provider)
    if provider_cls is None:
        raise EmbeddingError(
            f"Unknown embedding provider: {cfg.provider}",
            hint=f"Available providers: {', '.join(available_providers())}",
        )
    return provider_cls(cfg)
