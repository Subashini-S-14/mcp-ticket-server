"""
One-command demo launcher.

Seeds the database (if empty) and starts the AI Agent Client,
which connects to the MCP Server as a subprocess.

Usage:
    python scripts/run_demo.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config, setup_logging
from src.database.database import DatabaseManager
from src.database.seed import seed_database

logger = setup_logging()


async def ensure_database() -> None:
    """Ensure the database exists and has sample data."""
    db = DatabaseManager(Config.DATABASE_PATH)
    await db.initialize()

    row = await db.fetch_one("SELECT COUNT(*) as cnt FROM tickets")
    if row and row["cnt"] == 0:
        print("📦 Seeding database with sample data...")
        counts = await seed_database(db)
        print(f"   ✅ Seeded: {counts['tickets']} tickets, "
              f"{counts['comments']} comments, "
              f"{counts['kb_articles']} KB articles")
    else:
        print(f"📦 Database ready ({row['cnt']} tickets found)")

    await db.close()


def main() -> None:
    """Main entry point for the demo."""
    print("\n" + "=" * 60)
    print("🚀  AI-Powered Ticket Management MCP Server — Demo")
    print("=" * 60)

    # Check configuration
    issues = Config.validate()
    if issues:
        print("\n⚠️  Configuration issues detected:")
        for issue in issues:
            print(f"   • {issue}")
        print("\n   Please configure your .env file (see .env.example)")
        print("   Then run this script again.\n")
        return

    # Ensure database is ready
    print(f"\n🗄️  Database: {Config.DATABASE_PATH}")
    asyncio.run(ensure_database())

    # Launch agent client
    print(f"\n🤖 LLM Provider: {Config.LLM_PROVIDER} ({Config.LLM_MODEL})")
    print("   Starting agent client...\n")

    from src.client.agent_client import main as agent_main
    agent_main()


if __name__ == "__main__":
    main()
