"""Semantic roles for document blocks and sections.

A role answers *what a piece of text is for*, which is a different question
from *what it looks like* (:class:`~ragforge.models.document.BlockType`).

The distinction that matters most for RAG is:

``KNOWLEDGE``
    Prose, procedures, rules, examples, definitions - text that answers a
    question. This is what belongs in an embedding.

``RETRIEVAL_TERMS``
    Keyword dumps, tag lists, search aliases, entity lists. Genuinely useful
    for *finding* knowledge, but embedding a list of 300 near-synonyms produces
    a vector that matches everything and explains nothing.

``DOCUMENT_META``
    Front-matter about the document itself (chunk id, category, difficulty,
    authoring instructions). Rarely a useful retrieval target.

Nothing is discarded: retrieval terms become structured metadata fields on the
neighbouring knowledge chunks, and document metadata is preserved as a chunk
marked with its role so it can be filtered rather than lost.
"""

from __future__ import annotations

from enum import Enum


class SemanticRole(str, Enum):
    """What a block or section contributes to a retrieval system."""

    KNOWLEDGE = "knowledge"
    """Explanatory content that can answer a question."""

    DEFINITION = "definition"
    """A term paired with its meaning. Knowledge, but densely packed."""

    PROCEDURE = "procedure"
    """Ordered steps. Must stay in order and stay together."""

    EXAMPLE = "example"
    """An illustration of a concept. Needs its parent concept for context."""

    RULE = "rule"
    """Normative statements, constraints, best practices, mistakes."""

    REFERENCE = "reference"
    """Tables, comparison matrices, parameter listings."""

    CODE = "code"
    """Source code, pseudocode or textual diagrams."""

    RETRIEVAL_TERMS = "retrieval_terms"
    """Keyword / tag / alias / entity lists - metadata, not knowledge."""

    DOCUMENT_META = "document_meta"
    """Front-matter about the document itself."""

    NAVIGATION = "navigation"
    """Tables of contents, index links, 'see also' pointers."""

    @property
    def is_knowledge(self) -> bool:
        """True when the role should produce an ordinary retrievable chunk."""
        return self in _KNOWLEDGE_ROLES

    @property
    def is_auxiliary(self) -> bool:
        """True when the role is retrieval support rather than knowledge."""
        return self in {
            SemanticRole.RETRIEVAL_TERMS,
            SemanticRole.DOCUMENT_META,
            SemanticRole.NAVIGATION,
        }

    @property
    def needs_parent_context(self) -> bool:
        """True when the role is meaningless without its parent concept."""
        return self in {SemanticRole.EXAMPLE, SemanticRole.CODE}


_KNOWLEDGE_ROLES = frozenset(
    {
        SemanticRole.KNOWLEDGE,
        SemanticRole.DEFINITION,
        SemanticRole.PROCEDURE,
        SemanticRole.EXAMPLE,
        SemanticRole.RULE,
        SemanticRole.REFERENCE,
        SemanticRole.CODE,
    }
)


class TermField(str, Enum):
    """Structured metadata field a retrieval-term section maps onto."""

    KEYWORDS = "keywords"
    TAGS = "tags"
    ALIASES = "aliases"
    ENTITIES = "entities"
    RELATED_CONCEPTS = "related_concepts"
    QUESTIONS = "questions"
    """Anticipated user questions - excellent for query-side matching."""
