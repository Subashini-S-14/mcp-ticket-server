"""
MCP Server entry point for the AI-Powered Ticket Management system.

Registers all 5 MCP tools with the official Python MCP SDK and
serves them over stdio transport. Each tool delegates to the
appropriate service layer handler.

Usage:
    python -m src.server.mcp_server
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.config import Config, setup_logging
from src.database.database import DatabaseManager
from src.database.seed import seed_database
from src.services.kb_service import KBService
from src.services.ticket_service import TicketService
from src.server.tools.ticket_tools import (
    handle_add_comment,
    handle_create_ticket,
    handle_get_ticket,
    handle_list_tickets,
    handle_update_ticket_status,
    handle_resolve_ticket,
)
from src.server.tools.kb_tools import handle_search_kb

logger = setup_logging()

# ---------------------------------------------------------------------------
# Tool Schemas — defines the 5 MCP tools with JSON Schema input definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    Tool(
        name="list_tickets",
        description=(
            "List all support tickets with optional filtering. "
            "Returns ticket summaries (ID, title, status, priority, category). "
            "Use this to get an overview of tickets or find specific ones."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "resolved", "closed"],
                    "description": "Filter by ticket status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter by priority level",
                },
                "category": {
                    "type": "string",
                    "enum": ["bug", "feature", "question", "other"],
                    "description": "Filter by ticket category",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_ticket",
        description=(
            "Retrieve the full details of a single support ticket by its ID, "
            "including all associated comments. Use this when you need the "
            "complete context of a specific ticket."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The unique ID of the ticket to retrieve (e.g., TKT-abc123)",
                },
            },
            "required": ["ticket_id"],
        },
    ),
    Tool(
        name="create_ticket",
        description=(
            "Create a new support ticket. Use this when a user reports an issue, "
            "requests a feature, or asks a question that needs tracking. "
            "Returns the newly created ticket with its generated ID."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Brief summary of the issue (max 200 characters)",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue or request",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Priority level (default: medium)",
                },
                "category": {
                    "type": "string",
                    "enum": ["bug", "feature", "question", "other"],
                    "description": "Ticket category (default: other)",
                },
                "created_by": {
                    "type": "string",
                    "description": "Name or email of the ticket creator",
                },
            },
            "required": ["title", "description", "created_by"],
        },
    ),
    Tool(
        name="add_comment",
        description=(
            "Add a comment to an existing support ticket. Use this to append "
            "notes, updates, or responses to a ticket's conversation thread."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ID of the ticket to comment on",
                },
                "author": {
                    "type": "string",
                    "description": "Name or identifier of the comment author",
                },
                "content": {
                    "type": "string",
                    "description": "The comment text to add",
                },
            },
            "required": ["ticket_id", "author", "content"],
        },
    ),
    Tool(
        name="search_kb",
        description=(
            "Search the knowledge base for articles matching a query. "
            "Uses full-text search with relevance ranking. Use this to find "
            "existing solutions, documentation, or FAQs before creating tickets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (natural language supported)",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter for KB articles",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 5, max: 20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="update_ticket_status",
        description=(
            "Update the status of an existing support ticket. "
            "Use this to move a ticket through its lifecycle stages."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ID of the ticket to update",
                },
                "status": {
                    "type": "string",
                    "enum": ["Open", "In Progress", "Resolved", "Closed"],
                    "description": "The new status value",
                },
            },
            "required": ["ticket_id", "status"],
        },
    ),
    Tool(
        name="resolve_ticket",
        description=(
            "Automatically update a ticket's status to Resolved and record a "
            "resolution timestamp. Use this when an issue has been successfully addressed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ID of the ticket to resolve",
                },
            },
            "required": ["ticket_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Server Setup & Main
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Initialize the database, services, and start the MCP server."""

    # --- Initialize database ---
    db = DatabaseManager(Config.DATABASE_PATH)
    await db.initialize()

    # Seed with sample data if database is empty
    row = await db.fetch_one("SELECT COUNT(*) as cnt FROM tickets")
    if row and row["cnt"] == 0:
        logger.info("Database is empty — seeding with sample data...")
        counts = await seed_database(db)
        logger.info(f"Seeded: {counts}")

    # --- Initialize services ---
    ticket_service = TicketService(db)
    kb_service = KBService(db)

    # --- Create MCP Server ---
    server = Server("ticket-management-server")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return all available tool definitions."""
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Route tool calls to the appropriate handler."""
        logger.info(f"Tool called: {name} with args: {arguments}")

        try:
            if name == "list_tickets":
                result = await handle_list_tickets(
                    ticket_service,
                    status=arguments.get("status"),
                    priority=arguments.get("priority"),
                    category=arguments.get("category"),
                )
            elif name == "get_ticket":
                result = await handle_get_ticket(
                    ticket_service,
                    ticket_id=arguments.get("ticket_id", ""),
                )
            elif name == "create_ticket":
                result = await handle_create_ticket(
                    ticket_service,
                    title=arguments.get("title", ""),
                    description=arguments.get("description", ""),
                    created_by=arguments.get("created_by", ""),
                    priority=arguments.get("priority", "medium"),
                    category=arguments.get("category", "other"),
                )
            elif name == "add_comment":
                result = await handle_add_comment(
                    ticket_service,
                    ticket_id=arguments.get("ticket_id", ""),
                    author=arguments.get("author", ""),
                    content=arguments.get("content", ""),
                )
            elif name == "search_kb":
                result = await handle_search_kb(
                    kb_service,
                    query=arguments.get("query", ""),
                    category=arguments.get("category"),
                    limit=arguments.get("limit", 5),
                )
            elif name == "update_ticket_status":
                result = await handle_update_ticket_status(
                    ticket_service,
                    ticket_id=arguments.get("ticket_id", ""),
                    status=arguments.get("status", ""),
                )
            elif name == "resolve_ticket":
                result = await handle_resolve_ticket(
                    ticket_service,
                    ticket_id=arguments.get("ticket_id", ""),
                )
            else:
                result = f'{{"error": "Unknown tool: {name}", "error_code": "UNKNOWN_TOOL"}}'

            return [TextContent(type="text", text=result)]

        except Exception as e:
            logger.exception(f"Unhandled error in tool {name}")
            error_msg = f'{{"error": "Internal server error", "error_code": "INTERNAL_ERROR", "details": "{str(e)}"}}'
            return [TextContent(type="text", text=error_msg)]

    # --- Start stdio server ---
    logger.info("Starting MCP server (stdio transport)...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

    # Cleanup
    await db.close()


def main() -> None:
    """Entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as e:
        logger.exception(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
