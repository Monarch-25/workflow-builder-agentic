"""Standalone configuration for the Phase 2 orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


@dataclass(slots=True)
class Config:
    """Environment-backed settings needed by the Phase 2 orchestrator."""

    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_CLAUDE_MODEL: str = os.getenv(
        "BEDROCK_CLAUDE_MODEL",
        "anthropic.claude-sonnet-4-5",
    )
    BEDROCK_EMBED_MODEL: str = os.getenv(
        "BEDROCK_EMBED_MODEL",
        "amazon.titan-embed-text-v2:0",
    )
    BEDROCK_ADVANCED_TOOL_BETA: str = os.getenv(
        "BEDROCK_ADVANCED_TOOL_BETA",
        "advanced-tool-use-2025-11-20",
    )
    LOG_LLM_REQUESTS: bool = _get_bool("LOG_LLM_REQUESTS", False)

    REDIS_URL: str | None = os.getenv("REDIS_URL")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = _get_int("REDIS_PORT", 6379)
    REDIS_DB: int = _get_int("REDIS_DB", 0)

    BASE_DIR: Path = Path(
        os.getenv("BASE_DIR", str(Path.home() / ".workflow_engine"))
    )
    TASK_CACHE_TTL_SEC: int = _get_int("TASK_CACHE_TTL_SEC", 86400)
    VSS_TOP_K: int = _get_int("VSS_TOP_K", 15)
    EMBEDDING_DIM: int = _get_int("EMBEDDING_DIM", 1536)

    SANDBOX_TIMEOUT_SEC: int = _get_int("SANDBOX_TIMEOUT_SEC", 30)
    SANDBOX_MAX_MEMORY_MB: int = _get_int("SANDBOX_MAX_MEMORY_MB", 512)
    SANDBOX_MAX_CPU_SEC: int = _get_int("SANDBOX_MAX_CPU_SEC", 20)

    ORCHESTRATOR_DEFAULT_TRANSPORT: str = os.getenv(
        "ORCHESTRATOR_DEFAULT_TRANSPORT",
        "invoke_model",
    )
    ORCHESTRATOR_ENABLE_PROMPT_CACHING: bool = _get_bool(
        "ORCHESTRATOR_ENABLE_PROMPT_CACHING",
        False,
    )
    ORCHESTRATOR_MAX_SEARCH_ROUNDS: int = _get_int(
        "ORCHESTRATOR_MAX_SEARCH_ROUNDS",
        3,
    )
    ORCHESTRATOR_CANDIDATE_TOP_K: int = _get_int(
        "ORCHESTRATOR_CANDIDATE_TOP_K",
        8,
    )
    ORCHESTRATOR_MIN_CANDIDATES: int = _get_int(
        "ORCHESTRATOR_MIN_CANDIDATES",
        3,
    )
    ORCHESTRATOR_ANCHOR_TASK_IDS: str = os.getenv(
        "ORCHESTRATOR_ANCHOR_TASK_IDS",
        "upload_file_v1,return_output_v1,log_error_v1",
    )
    ORCHESTRATOR_TRACE_ENABLED: bool = _get_bool(
        "ORCHESTRATOR_TRACE_ENABLED",
        True,
    )

    @property
    def anchor_task_ids(self) -> tuple[str, ...]:
        """Return anchor task ids as a normalized tuple."""
        return tuple(
            task_id.strip()
            for task_id in self.ORCHESTRATOR_ANCHOR_TASK_IDS.split(",")
            if task_id.strip()
        )
