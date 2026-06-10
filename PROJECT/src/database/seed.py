"""
Database seeder — loads sample data from JSON files into SQLite.

Populates the tickets, comments, and kb_articles tables with
realistic sample data for demo purposes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.database.database import DatabaseManager

logger = logging.getLogger("ticket_mcp.seed")


def _generate_timestamps(index: int) -> tuple[str, str]:
    """Generate realistic created_at and updated_at timestamps."""
    base = datetime(2025, 6, 1, 9, 0, 0)
    created = base + timedelta(hours=index * 8, minutes=index * 13)
    updated = created + timedelta(hours=index * 2, minutes=30)
    return created.isoformat(), updated.isoformat()


async def seed_database(db: DatabaseManager, data_dir: str | Path | None = None) -> dict[str, int]:
    """
    Load sample data into the database.

    Args:
        db: An initialized DatabaseManager instance.
        data_dir: Path to the directory containing sample JSON files.
                  Defaults to the project's ``data/`` directory.

    Returns:
        A dict with counts of seeded entities, e.g.
        ``{"tickets": 8, "comments": 7, "kb_articles": 8}``.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    counts: dict[str, int] = {"tickets": 0, "comments": 0, "kb_articles": 0}

    # --- Load ticket data ---
    tickets_file = data_dir / "sample_tickets.json"
    if tickets_file.exists():
        with open(tickets_file, "r", encoding="utf-8") as f:
            ticket_data: dict[str, Any] = json.load(f)

        # Seed tickets
        for i, ticket in enumerate(ticket_data.get("tickets", [])):
            created_at, updated_at = _generate_timestamps(i)
            await db.execute(
                """INSERT OR IGNORE INTO tickets
                   (id, title, description, status, priority, category,
                    created_by, assigned_to, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket["id"],
                    ticket["title"],
                    ticket["description"],
                    ticket["status"],
                    ticket["priority"],
                    ticket["category"],
                    ticket["created_by"],
                    ticket.get("assigned_to"),
                    created_at,
                    updated_at,
                ),
            )
            counts["tickets"] += 1

        # Seed comments
        for j, comment in enumerate(ticket_data.get("comments", [])):
            created_at = (datetime(2025, 6, 2, 10, 0, 0) + timedelta(hours=j * 4)).isoformat()
            await db.execute(
                """INSERT OR IGNORE INTO comments
                   (id, ticket_id, author, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    comment["id"],
                    comment["ticket_id"],
                    comment["author"],
                    comment["content"],
                    created_at,
                ),
            )
            counts["comments"] += 1

        logger.info(f"Seeded {counts['tickets']} tickets, {counts['comments']} comments.")
    else:
        logger.warning(f"Sample tickets file not found: {tickets_file}")

    # --- Load KB data ---
    kb_file = data_dir / "sample_kb.json"
    if kb_file.exists():
        with open(kb_file, "r", encoding="utf-8") as f:
            kb_data: dict[str, Any] = json.load(f)

        for k, article in enumerate(kb_data.get("articles", [])):
            created_at = (datetime(2025, 5, 1, 9, 0, 0) + timedelta(days=k * 3)).isoformat()
            await db.execute(
                """INSERT OR IGNORE INTO kb_articles
                   (id, title, content, category, tags, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    article["id"],
                    article["title"],
                    article["content"],
                    article["category"],
                    article.get("tags"),
                    created_at,
                ),
            )
            counts["kb_articles"] += 1

        logger.info(f"Seeded {counts['kb_articles']} KB articles.")
    else:
        logger.warning(f"Sample KB file not found: {kb_file}")

    return counts
