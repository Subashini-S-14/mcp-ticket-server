"""
SQLite database connection manager and schema initialization.

Handles:
- Database connection lifecycle (async via aiosqlite)
- Schema creation (tables, indexes, FTS5 virtual table, triggers)
- Parameterized query execution
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger("ticket_mcp.database")

# ---------------------------------------------------------------------------
# SQL Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Tickets table
CREATE TABLE IF NOT EXISTS tickets (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    category    TEXT NOT NULL DEFAULT 'other'
                CHECK (category IN ('bug', 'feature', 'question', 'other')),
    created_by  TEXT NOT NULL,
    assigned_to TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id         TEXT PRIMARY KEY,
    ticket_id  TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author     TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Knowledge Base articles
CREATE TABLE IF NOT EXISTS kb_articles (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    category   TEXT NOT NULL,
    tags       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_comments_ticket_id ON comments(ticket_id);
"""

FTS_SCHEMA_SQL = """
-- Full-Text Search index for KB (SQLite FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS kb_articles_fts USING fts5(
    title,
    content,
    tags,
    content='kb_articles',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync with kb_articles table
CREATE TRIGGER IF NOT EXISTS kb_fts_ai AFTER INSERT ON kb_articles BEGIN
    INSERT INTO kb_articles_fts(rowid, title, content, tags)
    VALUES (new.rowid, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS kb_fts_ad AFTER DELETE ON kb_articles BEGIN
    INSERT INTO kb_articles_fts(kb_articles_fts, rowid, title, content, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS kb_fts_au AFTER UPDATE ON kb_articles BEGIN
    INSERT INTO kb_articles_fts(kb_articles_fts, rowid, title, content, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.tags);
    INSERT INTO kb_articles_fts(rowid, title, content, tags)
    VALUES (new.rowid, new.title, new.content, new.tags);
END;
"""


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------


class DatabaseManager:
    """
    Async SQLite database manager.

    Usage::

        db = DatabaseManager("./data/tickets.db")
        await db.initialize()
        rows = await db.fetch_all("SELECT * FROM tickets")
        await db.close()
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create the database, tables, indexes, and FTS5 virtual table."""
        # Ensure parent directory exists (unless in-memory)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        # Enable foreign key enforcement
        await self._connection.execute("PRAGMA foreign_keys = ON")
        # Enable WAL mode for better concurrent read performance
        await self._connection.execute("PRAGMA journal_mode = WAL")

        # Create core tables and indexes
        await self._connection.executescript(SCHEMA_SQL)

        # Migration: Add resolved_at column if it doesn't exist
        try:
            await self._connection.execute("ALTER TABLE tickets ADD COLUMN resolved_at TEXT")
        except aiosqlite.OperationalError:
            pass  # Column already exists

        # Create FTS5 virtual table and triggers (separate because executescript
        # can have issues with virtual table creation in some SQLite versions)
        for statement in FTS_SCHEMA_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                try:
                    await self._connection.execute(statement)
                except Exception as e:
                    # FTS5 tables may already exist; log and continue
                    logger.debug(f"FTS setup note: {e}")

        await self._connection.commit()
        logger.info(f"Database initialized: {self.db_path}")

    @property
    def connection(self) -> aiosqlite.Connection:
        """Return the active database connection."""
        if self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._connection

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement with parameters."""
        cursor = await self.connection.execute(sql, params)
        await self.connection.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        """Execute a query and return a single row as a dictionary."""
        self.connection.row_factory = aiosqlite.Row
        cursor = await self.connection.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dictionaries."""
        self.connection.row_factory = aiosqlite.Row
        cursor = await self.connection.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed.")
