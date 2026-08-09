"""Optional REST API and web inspection UI.

Requires the ``api`` extra::

    pip install "rag-chunkforge[api]"
    ragforge serve
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ragforge.api.app import app as app

__all__ = ["app", "create_app"]


def create_app() -> Any:
    """Build the FastAPI application (imported lazily)."""
    from ragforge.api.app import app as fastapi_app

    return fastapi_app


def __getattr__(name: str) -> Any:
    if name == "app":
        return create_app()
    raise AttributeError(f"module 'ragforge.api' has no attribute '{name}'")
