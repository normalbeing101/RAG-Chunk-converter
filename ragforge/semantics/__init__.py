"""Semantic role classification.

Separates *knowledge* (text that answers questions) from *retrieval metadata*
(keywords, tags, aliases, entities) and *document metadata* (front-matter),
so that each is represented in the way that actually helps retrieval.
"""

from ragforge.semantics.classifier import (
    RoleAssignment,
    RoleClassifier,
    Shape,
    extract_terms,
    heading_intent,
    measure_shape,
    normalize_heading,
)
from ragforge.semantics.roles import SemanticRole, TermField

__all__ = [
    "RoleAssignment",
    "RoleClassifier",
    "SemanticRole",
    "Shape",
    "TermField",
    "extract_terms",
    "heading_intent",
    "measure_shape",
    "normalize_heading",
]
