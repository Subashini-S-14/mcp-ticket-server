"""
Shared test fixtures for the AI Ticket MCP Server test suite.

Provides:
- In-memory SQLite database fixtures (isolated per test)
- Pre-configured service instances
- Sample data seeding
"""

import pytest
import pytest_asyncio

from src.database.database import DatabaseManager
from src.database.seed import seed_database
from src.services.ticket_service import TicketService
from src.services.kb_service import KBService


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database for isolated testing."""
    database = DatabaseManager(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def seeded_db():
    """In-memory SQLite database pre-loaded with sample data."""
    database = DatabaseManager(":memory:")
    await database.initialize()
    await seed_database(database)
    yield database
    await database.close()


@pytest_asyncio.fixture
async def ticket_service(seeded_db):
    """TicketService with a seeded test database."""
    return TicketService(seeded_db)


@pytest_asyncio.fixture
async def empty_ticket_service(db):
    """TicketService with an empty test database."""
    return TicketService(db)


@pytest_asyncio.fixture
async def kb_service(seeded_db):
    """KBService with a seeded test database."""
    return KBService(seeded_db)


@pytest_asyncio.fixture
async def empty_kb_service(db):
    """KBService with an empty test database."""
    return KBService(db)
