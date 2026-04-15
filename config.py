"""
Central configuration for OpsPilot AI.
Loads settings from environment variables / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Admin Panel
    ADMIN_PANEL_URL: str = os.getenv("ADMIN_PANEL_URL", "http://localhost:8000")
    ADMIN_PANEL_PORT: int = int(os.getenv("ADMIN_PANEL_PORT", "8000"))

    # Agent
    AGENT_HEADLESS: bool = os.getenv("AGENT_HEADLESS", "false").lower() == "true"
    AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "database/opspilot.db")


config = Config()
