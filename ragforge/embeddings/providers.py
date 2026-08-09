"""Built-in embedding providers.

``hash``
    Deterministic hashing embedding with no dependencies. Useful for testing
    pipelines, clustering smoke tests and offline demos - not for production
    semantic search.

``sentence-transformers`` / ``ollama`` / ``openai``
    Thin adapters around optional dependencies or HTTP APIs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Sequence
from typing import ClassVar

from ragforge.embeddings.base import EmbeddingProvider, register_provider
from ragforge.errors import EmbeddingError, MissingDependencyError
from ragforge.models.config import EmbeddingConfig


@register_provider
class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-words hashing embeddings (dependency-free)."""

    name: ClassVar[str] = "hash"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        dim = max(8, self.config.dimensions)
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * dim
            tokens = text.casefold().split()
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % dim
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(v * v for v in vector))
            vectors.append([v / norm for v in vector] if norm else vector)
        return vectors


@register_provider
class SentenceTransformersProvider(EmbeddingProvider):
    """Local models via ``sentence-transformers``."""

    name: ClassVar[str] = "sentence-transformers"

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        super().__init__(config)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MissingDependencyError(
                "sentence-transformers", "sentence-transformers embeddings"
            ) from exc
        model_name = self.config.model or "sentence-transformers/all-MiniLM-L6-v2"
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]

    @property
    def dimensions(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())


@register_provider
class OllamaProvider(EmbeddingProvider):
    """Embeddings from a local Ollama server."""

    name: ClassVar[str] = "ollama"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import urllib.error
        import urllib.request

        base = (self.config.base_url or "http://localhost:11434").rstrip("/")
        model = self.config.model or "nomic-embed-text"
        vectors: list[list[float]] = []
        for text in texts:
            payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
            request = urllib.request.Request(
                f"{base}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except urllib.error.URLError as exc:
                raise EmbeddingError(
                    f"Ollama request failed: {exc}",
                    hint=f"Is the Ollama server reachable at {base}?",
                ) from exc
            vector = data.get("embedding")
            if not isinstance(vector, list):
                raise EmbeddingError("Ollama response did not contain an 'embedding' array.")
            vectors.append([float(v) for v in vector])
        return vectors


@register_provider
class OpenAICompatibleProvider(EmbeddingProvider):
    """Any OpenAI-compatible ``/v1/embeddings`` endpoint."""

    name: ClassVar[str] = "openai"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import urllib.error
        import urllib.request

        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        model = self.config.model or "text-embedding-3-small"
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key:
            raise EmbeddingError(
                f"Missing API key: environment variable {self.config.api_key_env} is not set."
            )
        payload = json.dumps({"model": model, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            f"{base}/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise EmbeddingError(f"Embedding API returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise EmbeddingError(f"Embedding API request failed: {exc}") from exc
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [[float(v) for v in item["embedding"]] for item in items]
