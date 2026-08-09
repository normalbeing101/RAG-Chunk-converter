"""RAG ChunkForge - intelligent document chunking for retrieval-augmented generation.

Quick start::

    from ragforge import Pipeline, ForgeConfig

    config = ForgeConfig()
    result = Pipeline(config).run("docs/", write=False)
    print(result.statistics.total_chunks)
"""

from ragforge.chunking.engine import ChunkingEngine, available_strategies, chunk_text
from ragforge.errors import (
    ChunkingError,
    ConfigError,
    EmbeddingError,
    ExportError,
    InputError,
    MissingDependencyError,
    ParseError,
    RagForgeError,
    UnsupportedFormatError,
)
from ragforge.models import (
    Block,
    BlockType,
    Chunk,
    ChunkingConfig,
    ChunkMetadata,
    ChunkQuality,
    Document,
    ForgeConfig,
    ForgeResult,
    QualityFlag,
    Statistics,
    Strategy,
)
from ragforge.pipeline import Pipeline, discover_inputs, process

__version__ = "0.1.0"

__all__ = [
    "Block",
    "BlockType",
    "Chunk",
    "ChunkMetadata",
    "ChunkQuality",
    "ChunkingConfig",
    "ChunkingEngine",
    "ChunkingError",
    "ConfigError",
    "Document",
    "EmbeddingError",
    "ExportError",
    "ForgeConfig",
    "ForgeResult",
    "InputError",
    "MissingDependencyError",
    "ParseError",
    "Pipeline",
    "QualityFlag",
    "RagForgeError",
    "Statistics",
    "Strategy",
    "UnsupportedFormatError",
    "__version__",
    "available_strategies",
    "chunk_text",
    "discover_inputs",
    "process",
]
