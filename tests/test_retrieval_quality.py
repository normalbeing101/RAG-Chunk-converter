"""Retrieval-quality regression tests against the real knowledge document.

These are the tests that would have caught the original problem. They measure
*answerability*: given a realistic question, can a simple lexical retriever
find a chunk that actually contains the answer?

A keyword-dump chunk scores highly on term overlap but contains no answer, so
the checks assert both that the right chunk is retrieved **and** that it is a
knowledge chunk carrying explanatory prose.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import pytest

from ragforge import ForgeConfig, Pipeline
from ragforge.models.chunk import Chunk

FIXTURE = Path(__file__).parent / "fixtures" / "knowledge_document.md"

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset(
    """a an and are as at be by do does for from has have how in is it its of on or
    that the to was were what when where which who why will with does do can""".split()
)


def _terms(text: str) -> list[str]:
    return [w for w in (m.group(0).casefold() for m in _WORD_RE.finditer(text)) if w not in _STOP]


class BM25:
    """Minimal BM25 - stands in for a real retriever, no dependencies."""

    def __init__(self, docs: list[str], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [Counter(_terms(d)) for d in docs]
        self.lengths = [sum(c.values()) for c in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.df: Counter[str] = Counter()
        for doc in self.docs:
            self.df.update(doc.keys())
        self.n = len(self.docs)

    def rank(self, query: str, top: int = 5) -> list[tuple[int, float]]:
        q = _terms(query)
        scores: list[tuple[int, float]] = []
        for index, doc in enumerate(self.docs):
            length = self.lengths[index] or 1
            score = 0.0
            for term in q:
                freq = doc.get(term, 0)
                if not freq:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denominator = freq + self.k1 * (1 - self.b + self.b * length / (self.avg or 1))
                score += idf * freq * (self.k1 + 1) / denominator
            if score:
                scores.append((index, score))
        scores.sort(key=lambda item: -item[1])
        return scores[:top]


# question -> phrases that must appear in the retrieved answer
EVAL_SET: list[tuple[str, tuple[str, ...]]] = [
    (
        "What runtime is authoritative for current GDevelop behavior?",
        ("authoritative", "GDJS"),
    ),
    (
        "How does object picking affect subsequent actions?",
        ("picked", "conditions"),
    ),
    (
        "When are events evaluated?",
        ("every frame",),
    ),
    (
        "How do scene variables differ from global variables?",
        ("scene", "global"),
    ),
    (
        "What happens when an object is destroyed?",
        ("destro", "invalid"),
    ),
    (
        "How do sub-events depend on their parent event?",
        ("sub-event", "parent"),
    ),
    (
        "How does Wait affect event-sheet execution?",
        ("Wait", "continues"),
    ),
    (
        "What happens to the current scene when the scene changes?",
        ("unload",),
    ),
    (
        "When do behaviors run relative to events?",
        ("doStepPreEvents",),
    ),
    (
        "Do scene timers count up or down?",
        ("upward",),
    ),
]


@pytest.fixture(scope="module")
def chunks() -> list[Chunk]:
    if not FIXTURE.exists():  # pragma: no cover - fixture ships with the repo
        pytest.skip("knowledge document fixture is missing")
    return Pipeline(ForgeConfig()).run(FIXTURE, write=False).chunks


@pytest.fixture(scope="module")
def index(chunks: list[Chunk]) -> BM25:
    return BM25([c.text_for_embedding for c in chunks])


@pytest.mark.parametrize(("question", "expected"), EVAL_SET, ids=lambda v: None)
def test_question_is_answerable_from_top_chunks(question, expected, chunks, index):
    """The answer must appear in the top 3 results, in a knowledge chunk."""
    hits = index.rank(question, top=3)
    assert hits, f"no chunk retrieved for: {question}"

    for position, _score in hits:
        chunk = chunks[position]
        haystack = chunk.content.casefold()
        if all(phrase.casefold() in haystack for phrase in expected):
            assert chunk.is_knowledge, (
                f"{question!r} was answered by a non-knowledge chunk "
                f"(role={chunk.metadata.semantic_role})"
            )
            return
    top = [chunks[p].metadata.section for p, _ in hits]
    pytest.fail(f"{question!r}: expected {expected} in top-3; got sections {top}")


def test_top_results_are_never_keyword_dumps(chunks, index):
    """No question should be answered by a term list."""
    for question, _ in EVAL_SET:
        best = index.rank(question, top=1)
        assert best
        chunk = chunks[best[0][0]]
        flags = {f.value for f in (chunk.quality.flags if chunk.quality else [])}
        assert "KEYWORD_HEAVY" not in flags, f"{question!r} retrieved a keyword dump"
        assert "ALIAS_HEAVY" not in flags
        assert "HEADING_ONLY" not in flags


def test_every_knowledge_chunk_carries_prose(chunks):
    """A retrievable chunk must contain at least one full sentence of prose."""
    for chunk in chunks:
        if not chunk.is_knowledge:
            continue
        body = "\n".join(
            line for line in chunk.content.split("\n") if not line.lstrip().startswith("#")
        ).strip()
        assert body, f"{chunk.id} is heading-only"


def test_retrieval_metadata_is_available_for_filtering(chunks):
    """Harvested terms are present as structured fields, not as chunk text."""
    knowledge = [c for c in chunks if c.is_knowledge]
    assert knowledge
    assert any(not c.retrieval.is_empty() for c in knowledge)
    # And the giant alias list is not sitting inside anybody's content.
    for chunk in chunks:
        assert "GDevelop event processing order" not in chunk.content


def test_no_information_was_lost(chunks):
    pipeline = Pipeline(ForgeConfig())
    result = pipeline.run(FIXTURE, write=False)
    coverage = result.statistics.coverage
    assert coverage["dropped_blocks"] == 0, coverage
    assert coverage["retention"] >= 0.999


def test_no_metadata_only_chunk_outranks_knowledge_for_a_real_question(chunks, index):
    question = "How does object picking affect subsequent actions?"
    best_index = index.rank(question, top=1)[0][0]
    assert chunks[best_index].is_knowledge


# ----------------------------------------------------------------------
# Dense retrieval - the mode RAG actually uses.
#
# BM25 discounts term dumps automatically through IDF, so lexical search hides
# the problem. Cosine similarity over embeddings does not: a chunk containing
# 300 near-synonyms of the document's subject sits close to *every* query about
# that subject. This is the measurement that showed the original defect.
# ----------------------------------------------------------------------
def _dense_rank(provider, vectors, query: str, top: int) -> list[int]:
    query_vector = provider.embed([query])[0]
    scores = [sum(a * b for a, b in zip(query_vector, v, strict=True)) for v in vectors]
    return sorted(range(len(scores)), key=lambda i: -scores[i])[:top]


def test_dense_retrieval_returns_no_term_dumps(chunks):
    from ragforge.embeddings import get_provider
    from ragforge.models.config import EmbeddingConfig
    from ragforge.semantics import measure_shape

    provider = get_provider(EmbeddingConfig(provider="hash", dimensions=512))
    vectors = provider.embed([c.text_for_embedding for c in chunks])

    polluted = 0
    slots = 0
    for question, _ in EVAL_SET:
        for position in _dense_rank(provider, vectors, question, top=5):
            slots += 1
            body = "\n".join(
                line
                for line in chunks[position].content.split("\n")
                if not line.lstrip().startswith("#")
            ).strip()
            if measure_shape(body).is_term_list:
                polluted += 1
    assert polluted == 0, f"{polluted}/{slots} dense top-5 slots were keyword dumps"
