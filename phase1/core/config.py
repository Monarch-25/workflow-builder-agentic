"""
Central configuration — all env vars and constants.
Reads from .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Config(BaseSettings):
    """Workflow Engine configuration, loaded from environment / .env file."""

    # ── AWS ──────────────────────────────────────────────────────────────────
    AWS_REGION: str = "us-east-1"
    BEDROCK_CLAUDE_MODEL: str = "anthropic.claude-sonnet-4-5"
    BEDROCK_EMBED_MODEL: str = "amazon.titan-embed-text-v2:0"
    BEDROCK_ADVANCED_TOOL_BETA: str = "advanced-tool-use-2025-11-20"
    LOG_LLM_REQUESTS: bool = False

    # ── Redis (local instance) ──────────────────────────────────────────────
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ── Local storage ───────────────────────────────────────────────────────
    BASE_DIR: Path = Path.home() / ".workflow_engine"

    # ── Repo ────────────────────────────────────────────────────────────────
    TASK_CACHE_TTL_SEC: int = 86400       # 24 h
    VSS_TOP_K: int = 15
    EMBEDDING_DIM: int = 1536             # Titan embedding dimension

    # ── Sandbox ─────────────────────────────────────────────────────────────
    SANDBOX_TIMEOUT_SEC: int = 30
    SANDBOX_MAX_MEMORY_MB: int = 512
    SANDBOX_MAX_CPU_SEC: int = 20

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
