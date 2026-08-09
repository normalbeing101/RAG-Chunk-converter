"""Utility tests: ids, tokenizer, text segmentation, embeddings."""

from __future__ import annotations

import pytest

from ragforge.embeddings import available_providers, get_provider
from ragforge.errors import EmbeddingError
from ragforge.models.chunk import Chunk
from ragforge.models.config import EmbeddingConfig, SizeUnit
from ragforge.utils.ids import chunk_id, content_hash, section_id, slugify, stable_id
from ragforge.utils.text import (
    alnum_ratio,
    collapse_blank_lines,
    is_sentence_end,
    normalize_quotes,
    normalize_whitespace,
    split_paragraphs,
    split_sentences,
    truncate,
    word_count,
)
from ragforge.utils.tokenizer import get_tokenizer, measure


# ---------------------------------------------------------------- ids
def test_stable_id_deterministic():
    assert stable_id("doc", "a", "b") == stable_id("doc", "a", "b")
    assert stable_id("doc", "a") != stable_id("doc", "b")
    assert stable_id("doc", "a").startswith("doc_")


def test_chunk_id_padding():
    assert chunk_id("doc_1", 42) == "doc_1_chunk_0042"
    assert chunk_id("doc_1", 12345) == "doc_1_chunk_12345"


def test_section_id_varies_by_path():
    assert section_id("d", ["A"], 1) != section_id("d", ["B"], 1)
    assert section_id("d", ["A"], 1) == section_id("d", ["A"], 1)


def test_content_hash_normalizes():
    assert content_hash("Hello   World") == content_hash("hello world")
    assert content_hash("a") != content_hash("b")


def test_slugify():
    assert slugify("Héllo, World! 123") == "hello-world-123"
    assert slugify("") == "untitled"


# ---------------------------------------------------------------- tokenizer
def test_heuristic_tokenizer_counts():
    tk = get_tokenizer()
    assert tk.count_tokens("") == 0
    assert tk.count_tokens("hello world") == 2
    assert tk.count_tokens("internationalization") > 2


def test_tokenizer_units():
    tk = get_tokenizer()
    text = "one two three"
    assert tk.count(text, SizeUnit.CHARACTERS) == len(text)
    assert tk.count(text, SizeUnit.WORDS) == 3
    assert tk.count(text, SizeUnit.TOKENS) == 3


def test_measure_helper():
    assert measure("abc", SizeUnit.CHARACTERS) == 3


def test_tokenizer_is_cached():
    assert get_tokenizer("heuristic") is get_tokenizer("heuristic")


def test_tiktoken_tokenizer_when_available():
    pytest.importorskip("tiktoken")
    tk = get_tokenizer("tiktoken:cl100k_base")
    assert tk.count_tokens("hello world") >= 2


# ---------------------------------------------------------------- text
def test_normalize_whitespace():
    assert normalize_whitespace("a  \t b \n c ") == "a b\nc"
    assert normalize_whitespace("a\n b", preserve_newlines=False) == "a b"
    assert normalize_whitespace("") == ""


def test_collapse_blank_lines():
    assert collapse_blank_lines("a\n\n\n\nb") == "a\n\nb"
    assert collapse_blank_lines("a\n\n\n\nb", max_consecutive=2) == "a\n\n\nb"


def test_normalize_quotes():
    assert normalize_quotes("\u201cx\u201d \u2014 \u2018y\u2019") == "\"x\" - 'y'"


def test_split_paragraphs():
    assert split_paragraphs("a\n\nb\n\n\nc") == ["a", "b", "c"]
    assert split_paragraphs("   ") == []


def test_word_count():
    assert word_count("one two  three") == 3
    assert word_count("") == 0


def test_is_sentence_end():
    assert is_sentence_end("Done.")
    assert is_sentence_end('He said "stop."')
    assert is_sentence_end("")
    assert not is_sentence_end("Incomplete and")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One. Two. Three.", 3),
        ("Use e.g. this. Then stop.", 2),
        ("Version 2.5 shipped. Great.", 2),
        ("Dr. Smith arrived. He left.", 2),
        ("No terminal punctuation", 1),
        ("", 0),
        ("Wait... really? Yes!", 2),
    ],
)
def test_split_sentences(text, expected):
    assert len(split_sentences(text)) == expected


def test_split_sentences_keeps_list_items_separate():
    sentences = split_sentences("- first item\n- second item\n- third item")
    assert len(sentences) == 3


def test_alnum_ratio():
    assert alnum_ratio("") == 0.0
    assert alnum_ratio("abc") == 1.0
    assert alnum_ratio("a|||") == 0.25


def test_truncate():
    assert truncate("short", 10) == "short"
    assert len(truncate("x" * 100, 20)) == 20
    assert truncate("a\n  b") == "a b"


# ---------------------------------------------------------------- embeddings
def test_available_providers():
    assert "hash" in available_providers()


def test_hash_provider_is_deterministic_and_normalized():
    provider = get_provider(EmbeddingConfig(provider="hash", dimensions=64))
    a, b = provider.embed(["hello world", "hello world"])
    assert a == b
    assert len(a) == 64
    assert abs(sum(v * v for v in a) - 1.0) < 1e-9


def test_hash_provider_distinguishes_texts():
    provider = get_provider(EmbeddingConfig(provider="hash", dimensions=64))
    a, b = provider.embed(["retrieval augmented generation", "sourdough bread baking"])
    assert a != b


def test_embed_chunks_attaches_vectors():
    provider = get_provider(EmbeddingConfig(provider="hash", dimensions=16, batch_size=2))
    chunks = [Chunk(id=f"c{i}", content=f"content number {i}") for i in range(5)]
    provider.embed_chunks(chunks)
    assert all(c.embedding and len(c.embedding) == 16 for c in chunks)


def test_embed_empty_list():
    provider = get_provider(EmbeddingConfig(provider="hash"))
    assert provider.embed_chunks([]) == []


def test_unknown_provider():
    with pytest.raises(EmbeddingError):
        get_provider(EmbeddingConfig(provider="nope"))
