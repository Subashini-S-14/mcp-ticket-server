"""
MCP tool handler for knowledge base search.

Implements the search_kb MCP tool that performs full-text search
over knowledge base articles using SQLite FTS5.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.services.kb_service import KBService

logger = logging.getLogger("ticket_mcp.tools.kb")


def _error_response(message: str, error_code: str, details: str = "") -> str:
    """Format a standardized error response as JSON."""
    payload: dict[str, Any] = {
        "error": message,
        "error_code": error_code,
    }
    if details:
        payload["details"] = details
    return json.dumps(payload, indent=2)


def _success_response(data: dict[str, Any]) -> str:
    """Format a standardized success response as JSON."""
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: search_kb
# ---------------------------------------------------------------------------


async def handle_search_kb(
    kb_service: KBService,
    query: str,
    category: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    Search knowledge base articles using full-text search.

    Args:
        kb_service: The KBService instance.
        query: Search query string (supports natural language).
        category: Optional category filter for KB articles.
        limit: Max number of results (default 5, max 20).

    Returns:
        JSON string with ranked search results and metadata.
    """
    try:
        result = await kb_service.search(
            query=query,
            category=category,
            limit=limit,
        )
        return _success_response({
            "results": [r.model_dump() for r in result.results],
            "total_results": result.total_results,
            "query": result.query,
        })
    except Exception as e:
        logger.exception("Unexpected error in search_kb")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))
