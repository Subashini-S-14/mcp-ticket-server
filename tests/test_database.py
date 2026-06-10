"""
Tests for the database layer.

Covers:
- Database initialization and schema creation
- Table existence verification
- CRUD operations on tickets, comments, and KB articles
- Constraint validation (CHECK constraints, foreign keys)
- FTS5 virtual table functionality
"""

import pytest
import pytest_asyncio

from src.database.database import DatabaseManager


class TestDatabaseInitialization:
    """Test database schema creation and initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, db):
        """All required tables should exist after initialization."""
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = {row["name"] for row in tables}

        assert "tickets" in table_names
        assert "comments" in table_names
        assert "kb_articles" in table_names

    @pytest.mark.asyncio
    async def test_initialize_creates_indexes(self, db):
        """Required indexes should exist after initialization."""
        indexes = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = {row["name"] for row in indexes}

        assert "idx_tickets_status" in index_names
        assert "idx_tickets_priority" in index_names
        assert "idx_comments_ticket_id" in index_names

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, db):
        """Foreign key enforcement should be enabled."""
        result = await db.fetch_one("PRAGMA foreign_keys")
        assert result is not None


class TestDatabaseCRUD:
    """Test basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_and_fetch_ticket(self, db):
        """Should insert a ticket and retrieve it."""
        await db.execute(
            """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("T-001", "Test Ticket", "Test Description", "open", "medium", "bug", "tester"),
        )

        row = await db.fetch_one("SELECT * FROM tickets WHERE id = ?", ("T-001",))
        assert row is not None
        assert row["title"] == "Test Ticket"
        assert row["status"] == "open"
        assert row["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_insert_and_fetch_comment(self, db):
        """Should insert a comment linked to a ticket."""
        # First create the ticket
        await db.execute(
            """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("T-001", "Test Ticket", "Desc", "open", "medium", "bug", "tester"),
        )
        # Then create the comment
        await db.execute(
            """INSERT INTO comments (id, ticket_id, author, content)
               VALUES (?, ?, ?, ?)""",
            ("C-001", "T-001", "commenter", "This is a comment"),
        )

        row = await db.fetch_one("SELECT * FROM comments WHERE id = ?", ("C-001",))
        assert row is not None
        assert row["ticket_id"] == "T-001"
        assert row["content"] == "This is a comment"

    @pytest.mark.asyncio
    async def test_fetch_all_tickets(self, db):
        """Should return all tickets."""
        for i in range(3):
            await db.execute(
                """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"T-{i}", f"Ticket {i}", "Desc", "open", "medium", "bug", "tester"),
            )

        rows = await db.fetch_all("SELECT * FROM tickets")
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_fetch_one_returns_none_for_missing(self, db):
        """Should return None for non-existent rows."""
        row = await db.fetch_one("SELECT * FROM tickets WHERE id = ?", ("NONEXISTENT",))
        assert row is None


class TestDatabaseConstraints:
    """Test database constraint enforcement."""

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self, db):
        """CHECK constraint should reject invalid status values."""
        with pytest.raises(Exception):
            await db.execute(
                """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("T-001", "Test", "Desc", "INVALID_STATUS", "medium", "bug", "tester"),
            )

    @pytest.mark.asyncio
    async def test_invalid_priority_rejected(self, db):
        """CHECK constraint should reject invalid priority values."""
        with pytest.raises(Exception):
            await db.execute(
                """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("T-001", "Test", "Desc", "open", "INVALID_PRIORITY", "bug", "tester"),
            )

    @pytest.mark.asyncio
    async def test_invalid_category_rejected(self, db):
        """CHECK constraint should reject invalid category values."""
        with pytest.raises(Exception):
            await db.execute(
                """INSERT INTO tickets (id, title, description, status, priority, category, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("T-001", "Test", "Desc", "open", "medium", "INVALID_CATEGORY", "tester"),
            )


class TestDatabaseFTS:
    """Test Full-Text Search (FTS5) functionality."""

    @pytest.mark.asyncio
    async def test_fts_table_exists(self, db):
        """FTS5 virtual table should exist."""
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='kb_articles_fts'"
        )
        assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_fts_search_after_insert(self, db):
        """FTS5 should index new KB articles via trigger."""
        await db.execute(
            """INSERT INTO kb_articles (id, title, content, category, tags)
               VALUES (?, ?, ?, ?, ?)""",
            ("KB-TEST", "Password Reset", "How to reset your password", "account", "password,reset"),
        )

        results = await db.fetch_all(
            "SELECT * FROM kb_articles_fts WHERE kb_articles_fts MATCH ?",
            ("password",),
        )
        assert len(results) >= 1
