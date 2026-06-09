"""
Ticket Service — business logic for ticket and comment operations.

Handles creation, retrieval, listing, and commenting on support tickets.
All validation and domain rules live here; the database layer is data-only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.database.database import DatabaseManager
from src.database.models import (
    Comment,
    CommentCreate,
    Ticket,
    TicketCreate,
    TicketListResponse,
    TicketWithComments,
)

logger = logging.getLogger("ticket_mcp.ticket_service")

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_CATEGORIES = {"bug", "feature", "question", "other"}


class TicketNotFoundError(Exception):
    """Raised when a ticket cannot be found by ID."""
    error_code = "TICKET_NOT_FOUND"


class ValidationError(Exception):
    """Raised when input validation fails."""
    error_code = "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# TicketService
# ---------------------------------------------------------------------------


class TicketService:
    """Business logic for ticket and comment management."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # --- Ticket Operations ---

    async def create_ticket(self, data: TicketCreate) -> Ticket:
        """
        Create a new support ticket.

        Args:
            data: Validated ticket creation data.

        Returns:
            The newly created Ticket with generated ID and timestamps.

        Raises:
            ValidationError: If required fields are missing or invalid.
        """
        # Validate inputs
        if not data.title or not data.title.strip():
            raise ValidationError("Title is required and cannot be empty.")
        if not data.description or not data.description.strip():
            raise ValidationError("Description is required and cannot be empty.")
        if not data.created_by or not data.created_by.strip():
            raise ValidationError("created_by is required and cannot be empty.")

        ticket_id = f"TKT-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        await self.db.execute(
            """INSERT INTO tickets
               (id, title, description, status, priority, category,
                created_by, assigned_to, created_at, updated_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                data.title.strip(),
                data.description.strip(),
                "open",
                data.priority.value,
                data.category.value,
                data.created_by.strip(),
                None,
                now,
                now,
                None,
            ),
        )

        logger.info(f"Created ticket {ticket_id}: {data.title}")

        return Ticket(
            id=ticket_id,
            title=data.title.strip(),
            description=data.description.strip(),
            status="open",
            priority=data.priority,
            category=data.category,
            created_by=data.created_by.strip(),
            assigned_to=None,
            created_at=now,
            updated_at=now,
            resolved_at=None,
        )

    async def get_ticket(self, ticket_id: str) -> TicketWithComments:
        """
        Retrieve a single ticket by ID, including all comments.

        Args:
            ticket_id: The ticket's unique identifier.

        Returns:
            TicketWithComments with the full ticket data and comment list.

        Raises:
            TicketNotFoundError: If no ticket exists with the given ID.
        """
        row = await self.db.fetch_one(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        )
        if row is None:
            raise TicketNotFoundError(f"No ticket found with ID '{ticket_id}'")

        # Fetch associated comments
        comment_rows = await self.db.fetch_all(
            "SELECT * FROM comments WHERE ticket_id = ? ORDER BY created_at ASC",
            (ticket_id,),
        )
        comments = [Comment(**c) for c in comment_rows]

        return TicketWithComments(**row, comments=comments)

    async def list_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> TicketListResponse:
        """
        List tickets with optional filtering.

        Args:
            status: Filter by status (open, in_progress, resolved, closed).
            priority: Filter by priority (low, medium, high, critical).
            category: Filter by category (bug, feature, question, other).

        Returns:
            TicketListResponse with matching tickets and total count.

        Raises:
            ValidationError: If a filter value is not in the allowed set.
        """
        # Validate filter values
        if status and status not in VALID_STATUSES:
            raise ValidationError(
                f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}"
            )
        if priority and priority not in VALID_PRIORITIES:
            raise ValidationError(
                f"Invalid priority '{priority}'. Must be one of: {', '.join(VALID_PRIORITIES)}"
            )
        if category and category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}"
            )

        # Build dynamic query
        conditions: list[str] = []
        params: list[str] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM tickets{where_clause} ORDER BY created_at DESC"

        rows = await self.db.fetch_all(query, tuple(params))
        tickets = [Ticket(**row) for row in rows]

        return TicketListResponse(tickets=tickets, total_count=len(tickets))

    async def update_ticket_status(self, ticket_id: str, status: str) -> dict[str, Any]:
        """
        Update the status of a ticket.

        Args:
            ticket_id: The ticket's unique identifier.
            status: The new status. Will be mapped to lowercase database enum values.

        Returns:
            Dict containing success status and message.

        Raises:
            ValidationError: If status is invalid.
            TicketNotFoundError: If ticket does not exist.
        """
        # Map input status to enum value
        status_map = {
            "open": "open",
            "in progress": "in_progress",
            "in_progress": "in_progress",
            "resolved": "resolved",
            "closed": "closed"
        }
        
        normalized_status = status_map.get(status.lower().strip())
        if not normalized_status:
            raise ValidationError(
                f"Invalid status '{status}'. Must be one of: Open, In Progress, Resolved, Closed."
            )

        # Verify ticket exists
        row = await self.db.fetch_one("SELECT id, status FROM tickets WHERE id = ?", (ticket_id,))
        if row is None:
            raise TicketNotFoundError(f"No ticket found with ID '{ticket_id}'")

        now = datetime.now(timezone.utc).isoformat()
        
        # If resolving, we might also want to set resolved_at, but we'll leave that to resolve_ticket
        # or do it here. Let's do it here as well for consistency.
        resolved_at_query = ", resolved_at = ?" if normalized_status == "resolved" else ""
        params = (normalized_status, now, now, ticket_id) if normalized_status == "resolved" else (normalized_status, now, ticket_id)

        await self.db.execute(
            f"UPDATE tickets SET status = ?, updated_at = ?{resolved_at_query} WHERE id = ?",
            params,
        )

        logger.info(f"Updated ticket {ticket_id} status to {status}")
        return {"success": True, "message": f"Ticket {ticket_id} status updated to {status}"}

    async def resolve_ticket(self, ticket_id: str) -> dict[str, Any]:
        """
        Automatically update the ticket status to Resolved and add a timestamp.

        Args:
            ticket_id: The ticket's unique identifier.

        Returns:
            Dict containing success status and message.

        Raises:
            TicketNotFoundError: If ticket does not exist.
            ValidationError: If ticket is already closed.
        """
        row = await self.db.fetch_one("SELECT id, status FROM tickets WHERE id = ?", (ticket_id,))
        if row is None:
            raise TicketNotFoundError(f"No ticket found with ID '{ticket_id}'")

        if row["status"] == "closed":
            raise ValidationError(f"Cannot resolve ticket {ticket_id} because it is already closed.")

        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tickets SET status = 'resolved', updated_at = ?, resolved_at = ? WHERE id = ?",
            (now, now, ticket_id),
        )

        logger.info(f"Resolved ticket {ticket_id}")
        return {"success": True, "message": f"Ticket {ticket_id} resolved successfully"}

    # --- Comment Operations ---

    async def add_comment(self, data: CommentCreate) -> Comment:
        """
        Add a comment to an existing ticket.

        Args:
            data: Validated comment creation data.

        Returns:
            The newly created Comment.

        Raises:
            TicketNotFoundError: If the referenced ticket does not exist.
            ValidationError: If required fields are missing.
        """
        if not data.content or not data.content.strip():
            raise ValidationError("Comment content is required and cannot be empty.")
        if not data.author or not data.author.strip():
            raise ValidationError("Comment author is required and cannot be empty.")

        # Verify ticket exists
        ticket = await self.db.fetch_one(
            "SELECT id FROM tickets WHERE id = ?", (data.ticket_id,)
        )
        if ticket is None:
            raise TicketNotFoundError(
                f"Cannot add comment: no ticket found with ID '{data.ticket_id}'"
            )

        comment_id = f"CMT-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        await self.db.execute(
            """INSERT INTO comments (id, ticket_id, author, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (comment_id, data.ticket_id, data.author.strip(), data.content.strip(), now),
        )

        # Update ticket's updated_at timestamp
        await self.db.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (now, data.ticket_id),
        )

        logger.info(f"Added comment {comment_id} to ticket {data.ticket_id}")

        return Comment(
            id=comment_id,
            ticket_id=data.ticket_id,
            author=data.author.strip(),
            content=data.content.strip(),
            created_at=now,
        )
