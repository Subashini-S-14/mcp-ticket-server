"""
Tests for the KBService.

Covers:
- Full-text search with matching results
- Search with category filtering
- Search with result limiting
- Empty query handling
- No-match queries
- Fallback LIKE search
"""

import pytest

from src.services.kb_service import KBService


class TestKBSearch:
    """Test knowledge base search functionality."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, kb_service):
        """Should return results for a matching query."""
        result = await kb_service.search("password reset")

        assert result.total_results > 0
        assert result.query == "password reset"
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_results_have_required_fields(self, kb_service):
        """Each result should have all required fields."""
        result = await kb_service.search("password")

        for r in result.results:
            assert r.id is not None
            assert r.title is not None
            assert r.content is not None
            assert r.category is not None

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, kb_service):
        """Should filter results by category."""
        result = await kb_service.search("guide", category="account")

        for r in result.results:
            assert r.category == "account"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, kb_service):
        """Should return at most 'limit' results."""
        result = await kb_service.search("guide", limit=2)

        assert len(result.results) <= 2

    @pytest.mark.asyncio
    async def test_search_limit_clamped_to_max(self, kb_service):
        """Limit should be clamped to 20 maximum."""
        result = await kb_service.search("guide", limit=100)

        assert len(result.results) <= 20

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, kb_service):
        """Empty query should return no results."""
        result = await kb_service.search("")

        assert result.total_results == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_search_whitespace_query_returns_empty(self, kb_service):
        """Whitespace-only query should return no results."""
        result = await kb_service.search("   ")

        assert result.total_results == 0

    @pytest.mark.asyncio
    async def test_search_content_truncated(self, kb_service):
        """Result content should be truncated to MAX_CONTENT_LENGTH."""
        result = await kb_service.search("troubleshooting")

        for r in result.results:
            assert len(r.content) <= KBService.MAX_CONTENT_LENGTH + 3  # +3 for "..."

    @pytest.mark.asyncio
    async def test_search_no_match(self, kb_service):
        """Query with no matching articles should return empty results."""
        result = await kb_service.search("xyznonexistentquery123")

        assert result.total_results == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_search_empty_database(self, empty_kb_service):
        """Search on empty database should return no results."""
        result = await empty_kb_service.search("password")

        assert result.total_results == 0


class TestKBSearchRelevance:
    """Test search result relevance and ordering."""

    @pytest.mark.asyncio
    async def test_results_have_relevance_score(self, kb_service):
        """Each result should have a relevance score."""
        result = await kb_service.search("password")

        for r in result.results:
            assert isinstance(r.relevance_score, float)

    @pytest.mark.asyncio
    async def test_specific_query_returns_relevant_article(self, kb_service):
        """A specific query should return the most relevant article."""
        result = await kb_service.search("SSO single sign-on configuration")

        assert result.total_results > 0
        # The SSO article should be in the results
        titles = [r.title for r in result.results]
        assert any("SSO" in t for t in titles)
