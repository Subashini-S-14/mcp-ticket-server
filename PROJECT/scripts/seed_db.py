"""
Standalone database seeder script.

Seeds the SQLite database with sample tickets, comments, and KB articles.
Can be run independently to reset/populate the database for demos.

Usage:
    python scripts/seed_db.py
    python scripts/seed_db.py --db-path ./data/tickets.db
"""

import asyncio
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config, setup_logging
from src.database.database import DatabaseManager
from src.database.seed import seed_database

logger = setup_logging()


async def main(db_path: str) -> None:
    """Initialize database and seed with sample data."""
    print(f"\n📦 Seeding database: {db_path}\n")

    db = DatabaseManager(db_path)
    await db.initialize()

    # Check existing data
    row = await db.fetch_one("SELECT COUNT(*) as cnt FROM tickets")
    existing_count = row["cnt"] if row else 0

    if existing_count > 0:
        print(f"⚠️  Database already has {existing_count} tickets.")
        response = input("   Clear and re-seed? (y/N): ").strip().lower()
        if response != "y":
            print("   Skipping seed. Database unchanged.")
            await db.close()
            return

        # Clear existing data
        await db.execute("DELETE FROM comments")
        await db.execute("DELETE FROM tickets")
        await db.execute("DELETE FROM kb_articles")
        print("   ✅ Cleared existing data.")

    counts = await seed_database(db)

    print(f"\n✅ Seeding complete!")
    print(f"   📋 Tickets:     {counts['tickets']}")
    print(f"   💬 Comments:    {counts['comments']}")
    print(f"   📚 KB Articles: {counts['kb_articles']}")
    print()

    await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the ticket database with sample data")
    parser.add_argument(
        "--db-path",
        default=Config.DATABASE_PATH,
        help=f"Path to SQLite database (default: {Config.DATABASE_PATH})",
    )
    args = parser.parse_args()

    asyncio.run(main(args.db_path))
