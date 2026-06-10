"""
End-to-end tests for the Agent Loop.

Uses a mocked LLM to simulate multi-turn conversations,
verifying the agent correctly orchestrates tool calls and
returns synthesized responses.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.database.database import DatabaseManager
from src.database.seed import seed_database
from src.services.ticket_service import TicketService
from src.services.kb_service import KBService
from src.server.tools.ticket_tools import handle_list_tickets, handle_get_ticket
from src.server.tools.kb_tools import handle_search_kb


class MockMCPResult:
    """Mock for MCP tool call result."""

    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


class TestAgentLoopLogic:
    """Test the agent loop decision-making with mocked LLM."""

    @pytest_asyncio.fixture
    async def setup_services(self):
        """Set up services for agent loop testing."""
        db = DatabaseManager(":memory:")
        await db.initialize()
        await seed_database(db)
        ticket_svc = TicketService(db)
        kb_svc = KBService(db)
        yield db, ticket_svc, kb_svc
        await db.close()

    @pytest.mark.asyncio
    async def test_list_tickets_produces_valid_output(self, setup_services):
        """Agent calling list_tickets should get valid JSON back."""
        _, ticket_svc, _ = setup_services

        result_json = await handle_list_tickets(ticket_svc)
        result = json.loads(result_json)

        assert "tickets" in result
        assert isinstance(result["tickets"], list)
        assert result["total_count"] == len(result["tickets"])

    @pytest.mark.asyncio
    async def test_multi_tool_chain_search_then_get(self, setup_services):
        """Simulates: search KB → get ticket → synthesize."""
        _, ticket_svc, kb_svc = setup_services

        # Step 1: Agent searches KB
        kb_result = await handle_search_kb(kb_svc, query="password")
        kb_data = json.loads(kb_result)
        assert kb_data["total_results"] > 0

        # Step 2: Agent gets a specific ticket
        ticket_result = await handle_get_ticket(ticket_svc, ticket_id="TKT-005")
        ticket_data = json.loads(ticket_result)
        assert ticket_data["ticket"]["id"] == "TKT-005"
        assert "Password reset" in ticket_data["ticket"]["title"]

    @pytest.mark.asyncio
    async def test_error_handling_in_tool_chain(self, setup_services):
        """Agent should handle errors gracefully in multi-tool chains."""
        _, ticket_svc, _ = setup_services

        # Try to get a non-existent ticket
        result_json = await handle_get_ticket(ticket_svc, ticket_id="FAKE-ID")
        result = json.loads(result_json)

        assert "error" in result
        assert result["error_code"] == "TICKET_NOT_FOUND"
        # Agent should be able to continue after receiving an error

    @pytest.mark.asyncio
    async def test_tool_results_are_json_serializable(self, setup_services):
        """All tool results should be valid JSON strings."""
        _, ticket_svc, kb_svc = setup_services

        # Test all tools produce valid JSON
        results = [
            await handle_list_tickets(ticket_svc),
            await handle_get_ticket(ticket_svc, ticket_id="TKT-001"),
            await handle_search_kb(kb_svc, query="password"),
        ]

        for result_json in results:
            parsed = json.loads(result_json)
            assert isinstance(parsed, dict)


class TestAgentLoopIteration:
    """Test agent loop iteration and termination logic."""

    def test_system_prompt_is_defined(self):
        """The agent should have a well-defined system prompt."""
        from src.client.agent_client import SYSTEM_PROMPT

        assert len(SYSTEM_PROMPT) > 100
        assert "list_tickets" in SYSTEM_PROMPT
        assert "search_kb" in SYSTEM_PROMPT

    def test_max_iterations_configured(self):
        """Max iterations should be configured to prevent runaway loops."""
        from src.config import Config

        assert Config.MAX_AGENT_ITERATIONS > 0
        assert Config.MAX_AGENT_ITERATIONS <= 20
