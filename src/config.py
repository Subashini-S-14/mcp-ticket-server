"""
Configuration management for the AI Ticket MCP Server.

Loads settings from environment variables with sensible defaults.
Uses python-dotenv to support .env files for local development.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


class Config:
    """Centralized configuration loaded from environment variables."""

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "tickets.db"))
    SAMPLE_DATA_DIR: Path = BASE_DIR / "data"

    # --- LLM Provider ---
    LLM_PROVIDER: ClassVar[str] = os.getenv("LLM_PROVIDER", "gemini").lower()
    LLM_MODEL: ClassVar[str] = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    OPENAI_API_KEY: ClassVar[str | None] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: ClassVar[str | None] = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY: ClassVar[str | None] = os.getenv("GEMINI_API_KEY")

    # --- Agent ---
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_llm_api_key(cls) -> str | None:
        """Return the API key for the configured LLM provider."""
        if cls.LLM_PROVIDER == "anthropic":
            return cls.ANTHROPIC_API_KEY
        if cls.LLM_PROVIDER == "gemini":
            return cls.GEMINI_API_KEY
        return cls.OPENAI_API_KEY

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return a list of warnings/errors."""
        issues = []
        if cls.LLM_PROVIDER not in ("openai", "anthropic", "gemini"):
            issues.append(f"Invalid LLM_PROVIDER: '{cls.LLM_PROVIDER}'. Use 'openai', 'anthropic', or 'gemini'.")
        if not cls.get_llm_api_key():
            issues.append(f"No API key set for LLM_PROVIDER='{cls.LLM_PROVIDER}'. Set the corresponding env var.")
        return issues


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("ticket_mcp")
