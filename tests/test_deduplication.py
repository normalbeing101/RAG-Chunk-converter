"""Deduplication tests."""

from __future__ import annotations

from ragforge.deduplication import Deduplicator, MinHash, exact_jaccard, jaccard, shingles
from ragforge.models.chunk import Chunk, ChunkMetadata
from ragforge.models.config import DeduplicationConfig

LOREM = (
    "Retrieval augmented generation combines a retriever with a generator to answer "
    "questions using an external corpus of documents and passages."
)


def make(idx: str, content: str, document_id: str = "d1") -> Chunk:
    return Chunk(id=idx, content=content, metadata=ChunkMetadata(document_id=document_id))


# ---------------------------------------------------------------- minhash
def test_shingles_of_identical_text_match():
    assert shingles(LOREM) == shingles(LOREM)


def test_shingles_handle_short_text():
    assert shingles("hi", size=5)
    assert shingles("") == set()


def test_minhash_similarity_estimates():
    mh = MinHash(num_perm=128)
    a = mh.signature(shingles(LOREM))
    b = mh.signature(shingles(LOREM))
    c = mh.signature(shingles("Completely different subject about baking sourdough bread today."))
    assert jaccard(a, b) == 1.0
    assert jaccard(a, c) < 0.3


def test_exact_jaccard_bounds():
    assert exact_jaccard(set(), set()) == 1.0
    assert exact_jaccard({1}, set()) == 0.0
    assert exact_jaccard({1, 2}, {1, 2}) == 1.0
    assert exact_jaccard({1, 2}, {2, 3}) == 1 / 3


# ---------------------------------------------------------------- exact
def test_exact_duplicates_flagged():
    chunks = [make("a", LOREM), make("b", LOREM), make("c", "Something entirely different here.")]
    result = Deduplicator().run(chunks)
    assert result.exact_duplicates == 1
    assert chunks[1].metadata.duplicate_of == "a"
    assert chunks[1].metadata.similarity == 1.0
    assert chunks[0].metadata.duplicate_of is None


def test_whitespace_and_case_insensitive_exact_match():
    chunks = [make("a", LOREM), make("b", "  " + LOREM.upper().replace(" ", "\n  ") + " ")]
    result = Deduplicator().run(chunks)
    assert result.exact_duplicates == 1


def test_duplicates_dropped_when_configured():
    cfg = DeduplicationConfig(action="drop")
    chunks = [make("a", LOREM), make("b", LOREM), make("c", "Distinct content about other topics.")]
    result = Deduplicator(cfg).run(chunks)
    assert result.removed == 1
    assert [c.id for c in result.chunks] == ["a", "c"]


# ---------------------------------------------------------------- near
NEAR_BASE = " ".join(
    f"Sentence number {i} explains a distinct aspect of retrieval augmented generation."
    for i in range(12)
)


def test_near_duplicates_detected():
    variant = NEAR_BASE.replace("Sentence number 3", "Sentence number three")
    chunks = [
        make("a", NEAR_BASE),
        make("b", variant),
        make("c", "Unrelated text about gardening tools and greenhouse maintenance schedules."),
    ]
    result = Deduplicator(DeduplicationConfig(similarity_threshold=0.8)).run(chunks)
    assert result.near_duplicates == 1
    assert chunks[1].metadata.duplicate_of == "a"
    assert 0.8 <= (chunks[1].metadata.similarity or 0) < 1.0
    assert chunks[2].metadata.duplicate_of is None


def test_distinct_text_not_flagged():
    chunks = [
        make("a", "Configuring the retriever requires an index and an embedding model."),
        make("b", "Baking sourdough needs a starter, flour, water, salt and patience."),
    ]
    result = Deduplicator(DeduplicationConfig(similarity_threshold=0.8)).run(chunks)
    assert result.total == 0


def test_short_chunks_ignored():
    chunks = [make("a", "tiny"), make("b", "tiny")]
    result = Deduplicator(DeduplicationConfig(min_length=40)).run(chunks)
    assert result.total == 0


def test_disabled_deduplication():
    chunks = [make("a", LOREM), make("b", LOREM)]
    result = Deduplicator(DeduplicationConfig(enabled=False)).run(chunks)
    assert result.total == 0
    assert all(c.metadata.duplicate_of is None for c in chunks)


def test_method_off():
    chunks = [make("a", LOREM), make("b", LOREM)]
    assert Deduplicator(DeduplicationConfig(method="off")).run(chunks).total == 0


def test_exact_only_method_skips_near():
    variant = NEAR_BASE.replace("Sentence number 3", "Sentence number three")
    chunks = [make("a", NEAR_BASE), make("b", variant)]
    result = Deduplicator(DeduplicationConfig(method="exact")).run(chunks)
    assert result.near_duplicates == 0


def test_document_scope_keeps_cross_document_repeats():
    chunks = [make("a", LOREM, "d1"), make("b", LOREM, "d2")]
    result = Deduplicator(DeduplicationConfig(scope="document")).run(chunks)
    assert result.total == 0
    assert [c.id for c in result.chunks] == ["a", "b"]


def test_document_scope_finds_within_document():
    chunks = [make("a", LOREM, "d1"), make("b", LOREM, "d1"), make("c", LOREM, "d2")]
    result = Deduplicator(DeduplicationConfig(scope="document")).run(chunks)
    assert result.exact_duplicates == 1


def test_single_chunk_is_noop():
    assert Deduplicator().run([make("a", LOREM)]).total == 0


def test_dedup_scales_to_many_chunks():
    chunks = [make(f"c{i}", f"{LOREM} Variation number {i} of the text.") for i in range(300)]
    chunks.append(make("dup", chunks[7].content))
    result = Deduplicator(DeduplicationConfig(similarity_threshold=0.95)).run(chunks)
    assert result.exact_duplicates == 1
    assert len(result.chunks) == 301
