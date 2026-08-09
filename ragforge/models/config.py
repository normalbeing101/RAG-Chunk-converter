"""Configuration models.

The whole pipeline is driven by a single :class:`ForgeConfig` object which can
be loaded from YAML/JSON, overridden by CLI flags, or built programmatically.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ragforge.errors import ConfigError


class Strategy(str, Enum):
    """Available chunking strategies."""

    STRUCTURAL = "structural"
    RECURSIVE = "recursive"
    SENTENCE = "sentence"
    CODE = "code"
    AUTO = "auto"


class SizeUnit(str, Enum):
    """Units used to measure chunk size."""

    CHARACTERS = "characters"
    WORDS = "words"
    TOKENS = "tokens"


class OverlapUnit(str, Enum):
    """Units used to express chunk overlap."""

    PERCENTAGE = "percentage"
    CHARACTERS = "characters"
    WORDS = "words"
    TOKENS = "tokens"
    SAME = "same"
    """Use the same unit as ``chunking.unit``."""


class OutputFormat(str, Enum):
    JSONL = "jsonl"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "rag-dataset"
    description: str = ""
    version: str = "0.1.0"


class ChunkingConfig(BaseModel):
    """Chunk sizing and strategy settings."""

    model_config = ConfigDict(extra="forbid")

    strategy: Strategy | str = Strategy.RECURSIVE
    """A built-in :class:`Strategy` or the name of a custom registered strategy."""
    target_size: int = Field(default=500, gt=0)
    min_size: int = Field(default=100, ge=0)
    max_size: int = Field(default=800, gt=0)
    overlap: float = Field(default=75, ge=0)
    unit: SizeUnit = SizeUnit.TOKENS
    overlap_unit: OverlapUnit = OverlapUnit.SAME
    tokenizer: str = "heuristic"
    """``heuristic`` (no deps) or ``tiktoken:<encoding>``."""
    respect_sentence_boundaries: bool = True
    keep_code_blocks_intact: bool = True
    keep_tables_intact: bool = True
    merge_small_chunks: bool = True
    split_on_headings: bool = True
    max_heading_depth_split: int = 6
    """Only headings up to this depth start a new section."""

    @property
    def strategy_name(self) -> str:
        return self.strategy.value if isinstance(self.strategy, Strategy) else str(self.strategy)

    @model_validator(mode="after")
    def _validate_sizes(self) -> Self:
        if isinstance(self.strategy, str):
            try:
                object.__setattr__(self, "strategy", Strategy(self.strategy))
            except ValueError:
                from ragforge.chunking.engine import available_strategies

                if self.strategy not in available_strategies():
                    raise ConfigError(
                        f"Unknown chunking strategy: {self.strategy}",
                        hint=f"Available strategies: {', '.join(available_strategies())}",
                    ) from None
        if self.max_size < self.min_size:
            raise ConfigError(
                "Invalid chunk size: maximum must be greater than minimum "
                f"(max_size={self.max_size}, min_size={self.min_size})."
            )
        if self.target_size > self.max_size:
            raise ConfigError(
                "Invalid chunk size: target must not exceed maximum "
                f"(target_size={self.target_size}, max_size={self.max_size})."
            )
        if self.target_size < self.min_size:
            raise ConfigError(
                "Invalid chunk size: target must not be smaller than minimum "
                f"(target_size={self.target_size}, min_size={self.min_size})."
            )
        if self.overlap_unit is OverlapUnit.PERCENTAGE and self.overlap >= 100:
            raise ConfigError("Invalid overlap: percentage overlap must be below 100.")
        if self.overlap_unit is not OverlapUnit.PERCENTAGE and self.overlap >= self.target_size:
            raise ConfigError(
                "Invalid overlap: overlap must be smaller than the target chunk size "
                f"(overlap={self.overlap}, target_size={self.target_size})."
            )
        return self

    def resolved_overlap(self) -> int:
        """Overlap expressed in the same unit as :attr:`unit`."""
        if self.overlap_unit is OverlapUnit.PERCENTAGE:
            return int(self.target_size * self.overlap / 100)
        return int(self.overlap)


class CleaningConfig(BaseModel):
    """Text normalisation options. Everything is opt-out-able."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    normalize_whitespace: bool = True
    collapse_blank_lines: bool = True
    normalize_unicode: bool = True
    unicode_form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFKC"
    normalize_quotes: bool = False
    strip_html_boilerplate: bool = True
    remove_headers: bool = False
    remove_footers: bool = False
    remove_navigation: bool = False
    remove_urls: bool = False
    repeated_line_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    """A line repeated on more than this fraction of pages/sections is boilerplate."""
    min_repeats_for_boilerplate: int = Field(default=3, ge=2)
    preserve_code_blocks: bool = True


class DeduplicationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    similarity_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    method: str = "minhash"
    """``exact``, ``minhash`` (default, scalable) or ``off``."""
    shingle_size: int = Field(default=5, ge=1)
    num_permutations: int = Field(default=64, ge=16)
    action: str = "flag"
    """``flag`` keeps duplicates but marks them, ``drop`` removes them."""
    scope: str = "global"
    """``global`` across all documents, or ``document``."""
    min_length: int = Field(default=40, ge=0)
    """Chunks shorter than this (characters) are ignored by dedup."""


class ContextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_heading_path: bool = True
    include_source: bool = True
    include_title: bool = True
    include_context_prefix: bool = True
    prepend_context_to_content: bool = False
    """When true the context prefix is embedded in ``content`` itself."""
    heading_separator: str = " > "
    include_neighbors: bool = True
    include_parents: bool = True
    parent_level: str = "section"
    """``section`` or ``document``."""


class QualityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    min_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    """Chunks below this score are dropped when ``drop_low_quality`` is set."""
    drop_low_quality: bool = False
    low_context_word_threshold: int = 12
    llm_evaluator: bool = False


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str = "hash"
    """``hash`` (dependency-free, deterministic), ``sentence-transformers``,
    ``ollama``, ``openai`` or a registered custom provider."""
    model: str = ""
    dimensions: int = 256
    batch_size: int = 32
    base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    embed_context_prefix: bool = True


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: OutputFormat = OutputFormat.JSONL
    path: str = "output"
    filename: str = "chunks"
    write_statistics: bool = True
    include_quality: bool = True
    pretty: bool = True
    overwrite: bool = True


class ForgeConfig(BaseModel):
    """Root configuration object."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    deduplication: DeduplicationConfig = Field(default_factory=DeduplicationConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ForgeConfig:
        if not data:
            return cls()
        if not isinstance(data, dict):
            raise ConfigError("Configuration root must be a mapping.")
        normalized = _normalize_aliases(data)
        try:
            return cls.model_validate(normalized)
        except ConfigError:
            raise
        except Exception as exc:  # pydantic ValidationError
            raise ConfigError(f"Invalid configuration: {_format_pydantic_error(exc)}") from exc

    @classmethod
    def load(cls, path: str | Path) -> ForgeConfig:
        """Load configuration from a YAML or JSON file."""
        import json

        file_path = Path(path)
        if not file_path.exists():
            raise ConfigError(f"Configuration file not found: {file_path}")
        text = file_path.read_text(encoding="utf-8")
        suffix = file_path.suffix.lower()
        try:
            if suffix in {".yaml", ".yml"}:
                import yaml

                data = yaml.safe_load(text)
            elif suffix == ".json":
                data = json.loads(text)
            else:
                raise ConfigError(
                    f"Unsupported configuration format: {suffix or file_path.name}. "
                    "Use .yaml, .yml or .json."
                )
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"Unable to parse configuration file {file_path}: {exc}") from exc
        return cls.from_mapping(data)

    @classmethod
    def discover(cls, start: str | Path | None = None) -> ForgeConfig | None:
        """Find ``ragforge.yaml`` (or variants) walking up from ``start``."""
        base = Path(start or Path.cwd()).resolve()
        if base.is_file():
            base = base.parent
        names = ("ragforge.yaml", "ragforge.yml", "ragforge.json", ".ragforge.yaml")
        for directory in [base, *base.parents]:
            for name in names:
                candidate = directory / name
                if candidate.is_file():
                    return cls.load(candidate)
        return None

    def to_yaml(self) -> str:
        import yaml

        return yaml.safe_dump(
            self.model_dump(mode="json"), sort_keys=False, allow_unicode=True, indent=2
        )


_ALIASES: dict[str, dict[str, str]] = {
    "deduplication": {"threshold": "similarity_threshold"},
    "chunking": {"size": "target_size", "chunk_size": "target_size"},
    "output": {"formats": "format"},
}


def _normalize_aliases(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    for section, mapping in _ALIASES.items():
        block = result.get(section)
        if isinstance(block, dict):
            block = dict(block)
            for old, new in mapping.items():
                if old in block and new not in block:
                    block[new] = block.pop(old)
            result[section] = block
    return result


def _format_pydantic_error(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return str(exc)
    parts = []
    for err in errors():
        loc = ".".join(str(item) for item in err.get("loc", ()))
        parts.append(f"{loc or 'config'}: {err.get('msg', 'invalid value')}")
    return "; ".join(parts)
