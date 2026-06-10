"""
Integration tests for MCP tool handlers.

Tests each of the 5 MCP tools end-to-end with a real (in-memory) database.
Verifies correct JSON output format, success responses, and error handling.
"""

import json

import pytest
import pytest_asyncio

from src.database.database import DatabaseManager
from src.database.seed import seed_database
from src.services.ticket_service import TicketService
from src.services.kb_service import KBService
from src.server.tools.ticket_tools import (
    handle_list_tickets,
    handle_create_ticket,
    handle_add_comment,
    handle_update_ticket_status,
    handle_resolve_ticket,
)
from src.server.tools.kb_tools import handle_search_kb


@pytest_asyncio.fixture
async def services():
    """Provide both services backed by a seeded in-memory database."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await seed_database(db)
    yield TicketService(db), KBService(db)
    await db.close()


class TestListTicketsTool:
    """Test the list_tickets MCP tool handler."""

    @pytest.mark.asyncio
    async def test_list_all_tickets(self, services):
        """Should return all tickets as valid JSON."""
        ticket_svc, _ = services
        result_json = await handle_list_tickets(ticket_svc)
        result = json.loads(result_json)

        assert "tickets" in result
        assert "total_count" in result
        assert result["total_count"] == 8

    @pytest.mark.asyncio
    async def test_list_tickets_with_status_filter(self, services):
        """Should filter by status and return valid JSON."""
        ticket_svc, _ = services
        result_json = await handle_list_tickets(ticket_svc, status="open")
        result = json.loads(result_json)

        assert result["total_count"] > 0
        for ticket in result["tickets"]:
            assert ticket["status"] == "open"

    @pytest.mark.asyncio
    async def test_list_tickets_with_invalid_filter(self, services):
        """Should return error JSON for invalid filter values."""
        ticket_svc, _ = services
        result_json = await handle_list_tickets(ticket_svc, status="bogus")
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "VALIDATION_ERROR"


class TestGetTicketTool:
    """Test the get_ticket MCP tool handler."""

    @pytest.mark.asyncio
    async def test_get_existing_ticket(self, services):
        """Should return full ticket details with comments."""
        ticket_svc, _ = services
        result_json = await handle_get_ticket(ticket_svc, ticket_id="TKT-001")
        result = json.loads(result_json)

        assert "ticket" in result
        assert result["ticket"]["id"] == "TKT-001"
        assert "comments" in result["ticket"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_ticket(self, services):
        """Should return error JSON for unknown ticket ID."""
        ticket_svc, _ = services
        result_json = await handle_get_ticket(ticket_svc, ticket_id="TKT-MISSING")
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "TICKET_NOT_FOUND"


class TestCreateTicketTool:
    """Test the create_ticket MCP tool handler."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, services):
        """Should create a ticket and return it with a success message."""
        ticket_svc, _ = services
        result_json = await handle_create_ticket(
            ticket_svc,
            title="New Bug Report",
            description="Found a critical issue",
            created_by="qa@example.com",
            priority="high",
            category="bug",
        )
        result = json.loads(result_json)

        assert "ticket" in result
        assert "message" in result
        assert result["message"] == "Ticket created successfully"
        assert result["ticket"]["title"] == "New Bug Report"
        assert result["ticket"]["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_ticket_with_defaults(self, services):
        """Should use default priority and category."""
        ticket_svc, _ = services
        result_json = await handle_create_ticket(
            ticket_svc,
            title="Basic Ticket",
            description="A simple request",
            created_by="user@example.com",
        )
        result = json.loads(result_json)

        assert result["ticket"]["priority"] == "medium"
        assert result["ticket"]["category"] == "other"

    @pytest.mark.asyncio
    async def test_create_ticket_empty_title_returns_error(self, services):
        """Should return error for empty title."""
        ticket_svc, _ = services
        result_json = await handle_create_ticket(
            ticket_svc,
            title="",
            description="Valid description",
            created_by="user@example.com",
        )
        result = json.loads(result_json)

        assert "error" in result


class TestAddCommentTool:
    """Test the add_comment MCP tool handler."""

    @pytest.mark.asyncio
    async def test_add_comment_success(self, services):
        """Should add a comment and return it with a success message."""
        ticket_svc, _ = services
        result_json = await handle_add_comment(
            ticket_svc,
            ticket_id="TKT-001",
            author="agent",
            content="Investigating the issue",
        )
        result = json.loads(result_json)

        assert "comment" in result
        assert "message" in result
        assert result["message"] == "Comment added successfully"
        assert result["comment"]["ticket_id"] == "TKT-001"

    @pytest.mark.asyncio
    async def test_add_comment_to_nonexistent_ticket(self, services):
        """Should return error for invalid ticket ID."""
        ticket_svc, _ = services
        result_json = await handle_add_comment(
            ticket_svc,
            ticket_id="TKT-MISSING",
            author="user",
            content="Hello",
        )
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "TICKET_NOT_FOUND"


class TestSearchKBTool:
    """Test the search_kb MCP tool handler."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, services):
        """Should return search results as valid JSON."""
        _, kb_svc = services
        result_json = await handle_search_kb(kb_svc, query="password reset")
        result = json.loads(result_json)

        assert "results" in result
        assert "total_results" in result
        assert "query" in result
        assert result["total_results"] > 0

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, services):
        """Should respect category filter."""
        _, kb_svc = services
        result_json = await handle_search_kb(
            kb_svc, query="guide", category="account"
        )
        result = json.loads(result_json)

        for r in result["results"]:
            assert r["category"] == "account"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, services):
        """Should return empty results for empty query."""
        _, kb_svc = services
        result_json = await handle_search_kb(kb_svc, query="")
        result = json.loads(result_json)

        assert result["total_results"] == 0

    @pytest.mark.asyncio
    async def test_search_no_matches(self, services):
        """Should return empty results for unmatched query."""
        _, kb_svc = services
        result_json = await handle_search_kb(kb_svc, query="xyznonexistent123")
        result = json.loads(result_json)

        assert result["total_results"] == 0


class TestUpdateTicketStatusTool:
    """Test the update_ticket_status MCP tool handler."""

    @pytest.mark.asyncio
    async def test_update_ticket_status_success(self, services):
        """Should return success message."""
        ticket_svc, _ = services
        result_json = await handle_update_ticket_status(
            ticket_svc, ticket_id="TKT-001", status="In Progress"
        )
        result = json.loads(result_json)

        assert "success" in result
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_ticket_status_invalid(self, services):
        """Should return validation error for invalid status."""
        ticket_svc, _ = services
        result_json = await handle_update_ticket_status(
            ticket_svc, ticket_id="TKT-001", status="InvalidStatus"
        )
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "VALIDATION_ERROR"


class TestResolveTicketTool:
    """Test the resolve_ticket MCP tool handler."""

    @pytest.mark.asyncio
    async def test_resolve_ticket_success(self, services):
        """Should return success message when resolving."""
        ticket_svc, _ = services
        result_json = await handle_resolve_ticket(
            ticket_svc, ticket_id="TKT-002"
        )
        result = json.loads(result_json)

        assert "success" in result
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_resolve_ticket_missing(self, services):
        """Should return not found error."""
        ticket_svc, _ = services
        result_json = await handle_resolve_ticket(
            ticket_svc, ticket_id="TKT-MISSING"
        )
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "TICKET_NOT_FOUND"
