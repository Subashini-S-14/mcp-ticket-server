"""
Knowledge Base Service — full-text search over KB articles using SQLite FTS5.

Provides ranked search results using BM25 scoring with optional
category filtering and result limiting.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.database.database import DatabaseManager
from src.database.models import KBSearchResponse, KBSearchResult

logger = logging.getLogger("ticket_mcp.kb_service")


class KBService:
    """Business logic for knowledge base search operations."""

    # Maximum content length returned in search results (characters)
    MAX_CONTENT_LENGTH = 500

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> KBSearchResponse:
        """
        Search knowledge base articles using full-text search.

        Uses SQLite FTS5 with BM25 ranking for relevance scoring.
        Results are ordered by relevance (most relevant first).

        Args:
            query: The search query string (supports natural language).
            category: Optional category filter.
            limit: Maximum number of results to return (default 5, max 20).

        Returns:
            KBSearchResponse with ranked results and metadata.
        """
        # Clamp limit to [1, 20]
        limit = max(1, min(limit, 20))

        if not query or not query.strip():
            return KBSearchResponse(results=[], total_results=0, query=query or "")

        # Clean query for FTS5 — wrap each word in quotes for phrase-safe search
        clean_query = query.strip()

        try:
            # Use FTS5 MATCH with BM25 ranking
            # bm25() returns negative values (more negative = more relevant)
            if category:
                rows = await self.db.fetch_all(
                    """SELECT kb.id, kb.title, kb.content, kb.category, kb.tags,
                              -bm25(kb_articles_fts) AS relevance_score
                       FROM kb_articles_fts fts
                       JOIN kb_articles kb ON kb.rowid = fts.rowid
                       WHERE kb_articles_fts MATCH ?
                         AND kb.category = ?
                       ORDER BY relevance_score DESC
                       LIMIT ?""",
                    (clean_query, category, limit),
                )
            else:
                rows = await self.db.fetch_all(
                    """SELECT kb.id, kb.title, kb.content, kb.category, kb.tags,
                              -bm25(kb_articles_fts) AS relevance_score
                       FROM kb_articles_fts fts
                       JOIN kb_articles kb ON kb.rowid = fts.rowid
                       WHERE kb_articles_fts MATCH ?
                       ORDER BY relevance_score DESC
                       LIMIT ?""",
                    (clean_query, limit),
                )
        except Exception as e:
            # FTS5 query syntax error — fall back to LIKE search
            logger.warning(f"FTS5 search failed for query '{clean_query}': {e}. Falling back to LIKE.")
            rows = await self._fallback_search(clean_query, category, limit)

        results = []
        for row in rows:
            content = row.get("content", "")
            # Truncate content for response
            if len(content) > self.MAX_CONTENT_LENGTH:
                content = content[: self.MAX_CONTENT_LENGTH] + "..."

            results.append(
                KBSearchResult(
                    id=row["id"],
                    title=row["title"],
                    content=content,
                    category=row["category"],
                    tags=row.get("tags"),
                    relevance_score=round(row.get("relevance_score", 0.0), 4),
                )
            )

        logger.info(f"KB search for '{clean_query}': {len(results)} results")

        return KBSearchResponse(
            results=results,
            total_results=len(results),
            query=query.strip(),
        )

    async def _fallback_search(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Fallback LIKE-based search when FTS5 query syntax is invalid."""
        like_pattern = f"%{query}%"

        if category:
            return await self.db.fetch_all(
                """SELECT id, title, content, category, tags, 0.0 AS relevance_score
                   FROM kb_articles
                   WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                     AND category = ?
                   LIMIT ?""",
                (like_pattern, like_pattern, like_pattern, category, limit),
            )
        else:
            return await self.db.fetch_all(
                """SELECT id, title, content, category, tags, 0.0 AS relevance_score
                   FROM kb_articles
                   WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                   LIMIT ?""",
                (like_pattern, like_pattern, like_pattern, limit),
            )
