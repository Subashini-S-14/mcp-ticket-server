"""
Tests for the TicketService.

Covers:
- Ticket creation (success + validation errors)
- Ticket retrieval by ID (found + not found)
- Ticket listing with filters
- Comment addition (success + ticket not found)
"""

import pytest

from src.database.models import CommentCreate, TicketCreate
from src.services.ticket_service import (
    TicketNotFoundError,
    TicketService,
    ValidationError,
)


class TestCreateTicket:
    """Test ticket creation."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, empty_ticket_service):
        """Should create a ticket with valid data and return it."""
        data = TicketCreate(
            title="Test Bug",
            description="Something is broken",
            priority="high",
            category="bug",
            created_by="tester@example.com",
        )
        ticket = await empty_ticket_service.create_ticket(data)

        assert ticket.id.startswith("TKT-")
        assert ticket.title == "Test Bug"
        assert ticket.description == "Something is broken"
        assert ticket.status == "open"
        assert ticket.priority == "high"
        assert ticket.category == "bug"
        assert ticket.created_by == "tester@example.com"
        assert ticket.assigned_to is None

    @pytest.mark.asyncio
    async def test_create_ticket_with_defaults(self, empty_ticket_service):
        """Should use default priority and category when not specified."""
        data = TicketCreate(
            title="Simple Ticket",
            description="A basic ticket",
            created_by="user@example.com",
        )
        ticket = await empty_ticket_service.create_ticket(data)

        assert ticket.priority == "medium"
        assert ticket.category == "other"

    @pytest.mark.asyncio
    async def test_create_ticket_empty_title_raises(self, empty_ticket_service):
        """Should raise ValidationError for empty title."""
        data = TicketCreate(
            title="   ",
            description="Valid description",
            created_by="user@example.com",
        )
        with pytest.raises(ValidationError, match="Title is required"):
            await empty_ticket_service.create_ticket(data)

    @pytest.mark.asyncio
    async def test_create_ticket_empty_description_raises(self, empty_ticket_service):
        """Should raise ValidationError for empty description."""
        data = TicketCreate(
            title="Valid Title",
            description="   ",
            created_by="user@example.com",
        )
        with pytest.raises(ValidationError, match="Description is required"):
            await empty_ticket_service.create_ticket(data)


class TestGetTicket:
    """Test ticket retrieval."""

    @pytest.mark.asyncio
    async def test_get_existing_ticket(self, ticket_service):
        """Should retrieve an existing ticket with comments."""
        ticket = await ticket_service.get_ticket("TKT-001")

        assert ticket.id == "TKT-001"
        assert ticket.title == "Login page returns 500 error"
        assert ticket.status == "open"
        assert ticket.priority == "critical"
        assert len(ticket.comments) >= 1  # Sample data has comments for TKT-001

    @pytest.mark.asyncio
    async def test_get_nonexistent_ticket_raises(self, ticket_service):
        """Should raise TicketNotFoundError for non-existent ID."""
        with pytest.raises(TicketNotFoundError):
            await ticket_service.get_ticket("TKT-NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_ticket_includes_comments(self, ticket_service):
        """Should include all comments for the ticket."""
        ticket = await ticket_service.get_ticket("TKT-001")

        assert hasattr(ticket, "comments")
        assert isinstance(ticket.comments, list)
        # TKT-001 has 3 comments in sample data
        assert len(ticket.comments) == 3
        for comment in ticket.comments:
            assert comment.ticket_id == "TKT-001"


class TestListTickets:
    """Test ticket listing with filters."""

    @pytest.mark.asyncio
    async def test_list_all_tickets(self, ticket_service):
        """Should return all tickets when no filters applied."""
        result = await ticket_service.list_tickets()

        assert result.total_count == 8  # Sample data has 8 tickets
        assert len(result.tickets) == 8

    @pytest.mark.asyncio
    async def test_list_tickets_filter_by_status(self, ticket_service):
        """Should filter tickets by status."""
        result = await ticket_service.list_tickets(status="open")

        assert result.total_count > 0
        for ticket in result.tickets:
            assert ticket.status == "open"

    @pytest.mark.asyncio
    async def test_list_tickets_filter_by_priority(self, ticket_service):
        """Should filter tickets by priority."""
        result = await ticket_service.list_tickets(priority="critical")

        assert result.total_count > 0
        for ticket in result.tickets:
            assert ticket.priority == "critical"

    @pytest.mark.asyncio
    async def test_list_tickets_filter_by_category(self, ticket_service):
        """Should filter tickets by category."""
        result = await ticket_service.list_tickets(category="bug")

        assert result.total_count > 0
        for ticket in result.tickets:
            assert ticket.category == "bug"

    @pytest.mark.asyncio
    async def test_list_tickets_combined_filters(self, ticket_service):
        """Should support multiple filters simultaneously."""
        result = await ticket_service.list_tickets(status="open", priority="high")

        for ticket in result.tickets:
            assert ticket.status == "open"
            assert ticket.priority == "high"

    @pytest.mark.asyncio
    async def test_list_tickets_invalid_status_raises(self, ticket_service):
        """Should raise ValidationError for invalid filter values."""
        with pytest.raises(ValidationError, match="Invalid status"):
            await ticket_service.list_tickets(status="invalid_status")

    @pytest.mark.asyncio
    async def test_list_tickets_empty_result(self, empty_ticket_service):
        """Should return empty list when no tickets exist."""
        result = await empty_ticket_service.list_tickets()

        assert result.total_count == 0
        assert result.tickets == []


class TestAddComment:
    """Test comment addition."""

    @pytest.mark.asyncio
    async def test_add_comment_success(self, ticket_service):
        """Should add a comment to an existing ticket."""
        data = CommentCreate(
            ticket_id="TKT-001",
            author="test-user",
            content="This is a test comment",
        )
        comment = await ticket_service.add_comment(data)

        assert comment.id.startswith("CMT-")
        assert comment.ticket_id == "TKT-001"
        assert comment.author == "test-user"
        assert comment.content == "This is a test comment"

    @pytest.mark.asyncio
    async def test_add_comment_updates_ticket_timestamp(self, ticket_service):
        """Adding a comment should update the ticket's updated_at."""
        ticket_before = await ticket_service.get_ticket("TKT-002")

        data = CommentCreate(
            ticket_id="TKT-002",
            author="updater",
            content="Updating this ticket",
        )
        await ticket_service.add_comment(data)

        ticket_after = await ticket_service.get_ticket("TKT-002")
        assert ticket_after.updated_at >= ticket_before.updated_at

    @pytest.mark.asyncio
    async def test_add_comment_to_nonexistent_ticket_raises(self, ticket_service):
        """Should raise TicketNotFoundError for invalid ticket ID."""
        data = CommentCreate(
            ticket_id="TKT-NONEXISTENT",
            author="user",
            content="Comment text",
        )
        with pytest.raises(TicketNotFoundError):
            await ticket_service.add_comment(data)

    @pytest.mark.asyncio
    async def test_add_comment_empty_content_raises(self, ticket_service):
        """Should raise ValidationError for empty comment content."""
        data = CommentCreate(
            ticket_id="TKT-001",
            author="user",
            content="   ",
        )
        with pytest.raises(ValidationError, match="content is required"):
            await ticket_service.add_comment(data)


class TestUpdateTicketStatus:
    """Test ticket status updates."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, ticket_service):
        """Should update ticket status and return success message."""
        result = await ticket_service.update_ticket_status("TKT-001", "Closed")
        assert result["success"] is True
        assert "Closed" in result["message"]

        ticket = await ticket_service.get_ticket("TKT-001")
        assert ticket.status == "closed"

    @pytest.mark.asyncio
    async def test_update_status_invalid_raises(self, ticket_service):
        """Should raise ValidationError for invalid status."""
        with pytest.raises(ValidationError, match="Invalid status"):
            await ticket_service.update_ticket_status("TKT-001", "Invalid")

    @pytest.mark.asyncio
    async def test_update_status_nonexistent_raises(self, ticket_service):
        """Should raise TicketNotFoundError for invalid ticket ID."""
        with pytest.raises(TicketNotFoundError):
            await ticket_service.update_ticket_status("TKT-NONEXISTENT", "Open")


class TestResolveTicket:
    """Test ticket resolution."""

    @pytest.mark.asyncio
    async def test_resolve_ticket_success(self, ticket_service):
        """Should resolve ticket, set timestamp, and return success."""
        result = await ticket_service.resolve_ticket("TKT-002")
        assert result["success"] is True

        ticket = await ticket_service.get_ticket("TKT-002")
        assert ticket.status == "resolved"
        assert ticket.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_closed_ticket_raises(self, ticket_service):
        """Should raise ValidationError when resolving an already closed ticket."""
        await ticket_service.update_ticket_status("TKT-001", "Closed")
        with pytest.raises(ValidationError, match="already closed"):
            await ticket_service.resolve_ticket("TKT-001")

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_raises(self, ticket_service):
        """Should raise TicketNotFoundError for invalid ticket ID."""
        with pytest.raises(TicketNotFoundError):
            await ticket_service.resolve_ticket("TKT-NONEXISTENT")
