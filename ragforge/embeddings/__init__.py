"""Optional embedding pipeline."""

from ragforge.embeddings.base import (
    EmbeddingProvider,
    available_providers,
    get_provider,
    register_provider,
)
from ragforge.embeddings.providers import (
    HashEmbeddingProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    SentenceTransformersProvider,
)

__all__ = [
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "SentenceTransformersProvider",
    "available_providers",
    "get_provider",
    "register_provider",
]
