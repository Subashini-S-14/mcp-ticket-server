"""
MCP tool handlers for ticket operations.

Implements the following MCP tools:
- list_tickets: Query tickets with optional filters
- get_ticket: Retrieve a single ticket with comments
- create_ticket: Create a new support ticket
- add_comment: Add a comment to an existing ticket

Each tool handler validates input, delegates to the TicketService,
and returns JSON-serialized responses following MCP conventions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.database.models import CommentCreate, TicketCreate
from src.services.ticket_service import (
    TicketNotFoundError,
    TicketService,
    ValidationError,
)

logger = logging.getLogger("ticket_mcp.tools.ticket")


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
# Tool: list_tickets
# ---------------------------------------------------------------------------


async def handle_list_tickets(
    ticket_service: TicketService,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """
    List all tickets with optional filtering by status, priority, or category.

    Args:
        ticket_service: The TicketService instance.
        status: Filter by ticket status.
        priority: Filter by priority level.
        category: Filter by ticket category.

    Returns:
        JSON string with tickets and total_count.
    """
    try:
        result = await ticket_service.list_tickets(
            status=status, priority=priority, category=category
        )
        return _success_response({
            "tickets": [t.model_dump() for t in result.tickets],
            "total_count": result.total_count,
        })
    except ValidationError as e:
        return _error_response(str(e), e.error_code)
    except Exception as e:
        logger.exception("Unexpected error in list_tickets")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Tool: get_ticket
# ---------------------------------------------------------------------------


async def handle_get_ticket(
    ticket_service: TicketService,
    ticket_id: str,
) -> str:
    """
    Retrieve a single ticket by ID, including all associated comments.

    Args:
        ticket_service: The TicketService instance.
        ticket_id: The UUID of the ticket to retrieve.

    Returns:
        JSON string with the full ticket and its comments.
    """
    try:
        ticket = await ticket_service.get_ticket(ticket_id)
        return _success_response({"ticket": ticket.model_dump()})
    except TicketNotFoundError as e:
        return _error_response(str(e), e.error_code, f"No ticket with ID '{ticket_id}' exists")
    except Exception as e:
        logger.exception("Unexpected error in get_ticket")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Tool: create_ticket
# ---------------------------------------------------------------------------


async def handle_create_ticket(
    ticket_service: TicketService,
    title: str,
    description: str,
    created_by: str,
    priority: str = "medium",
    category: str = "other",
) -> str:
    """
    Create a new support ticket.

    Args:
        ticket_service: The TicketService instance.
        title: Brief summary of the issue (max 200 chars).
        description: Detailed description of the issue.
        created_by: Name or identifier of the ticket creator.
        priority: Priority level (low, medium, high, critical).
        category: Ticket category (bug, feature, question, other).

    Returns:
        JSON string with the newly created ticket and a success message.
    """
    try:
        data = TicketCreate(
            title=title,
            description=description,
            priority=priority,
            category=category,
            created_by=created_by,
        )
        ticket = await ticket_service.create_ticket(data)
        return _success_response({
            "ticket": ticket.model_dump(),
            "message": "Ticket created successfully",
        })
    except ValidationError as e:
        return _error_response(str(e), e.error_code)
    except Exception as e:
        logger.exception("Unexpected error in create_ticket")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Tool: add_comment
# ---------------------------------------------------------------------------


async def handle_add_comment(
    ticket_service: TicketService,
    ticket_id: str,
    author: str,
    content: str,
) -> str:
    """
    Add a comment to an existing ticket.

    Args:
        ticket_service: The TicketService instance.
        ticket_id: The UUID of the ticket to comment on.
        author: Name or identifier of the comment author.
        content: The comment text.

    Returns:
        JSON string with the newly created comment and a success message.
    """
    try:
        data = CommentCreate(
            ticket_id=ticket_id,
            author=author,
            content=content,
        )
        comment = await ticket_service.add_comment(data)
        return _success_response({
            "comment": comment.model_dump(),
            "message": "Comment added successfully",
        })
    except TicketNotFoundError as e:
        return _error_response(str(e), e.error_code, f"No ticket with ID '{ticket_id}' exists")
    except ValidationError as e:
        return _error_response(str(e), e.error_code)
    except Exception as e:
        logger.exception("Unexpected error in add_comment")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Tool: update_ticket_status
# ---------------------------------------------------------------------------


async def handle_update_ticket_status(
    ticket_service: TicketService,
    ticket_id: str,
    status: str,
) -> str:
    """
    Update the status of an existing ticket.

    Args:
        ticket_service: The TicketService instance.
        ticket_id: The UUID of the ticket to update.
        status: The new status value (e.g., 'Open', 'In Progress', 'Resolved', 'Closed').

    Returns:
        JSON string with success status and message.
    """
    try:
        result = await ticket_service.update_ticket_status(ticket_id, status)
        return _success_response(result)
    except TicketNotFoundError as e:
        return _error_response(str(e), e.error_code, f"No ticket with ID '{ticket_id}' exists")
    except ValidationError as e:
        return _error_response(str(e), e.error_code)
    except Exception as e:
        logger.exception("Unexpected error in update_ticket_status")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Tool: resolve_ticket
# ---------------------------------------------------------------------------


async def handle_resolve_ticket(
    ticket_service: TicketService,
    ticket_id: str,
) -> str:
    """
    Automatically resolve a ticket and add a resolution timestamp.

    Args:
        ticket_service: The TicketService instance.
        ticket_id: The UUID of the ticket to resolve.

    Returns:
        JSON string with success status and message.
    """
    try:
        result = await ticket_service.resolve_ticket(ticket_id)
        return _success_response(result)
    except TicketNotFoundError as e:
        return _error_response(str(e), e.error_code, f"No ticket with ID '{ticket_id}' exists")
    except ValidationError as e:
        return _error_response(str(e), e.error_code)
    except Exception as e:
        logger.exception("Unexpected error in resolve_ticket")
        return _error_response("Internal server error", "INTERNAL_ERROR", str(e))
