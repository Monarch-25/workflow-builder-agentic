"""
Startup — initialise directories, Redis, LLM, and seed the task repo.

Usage:
    python startup.py

Requires:
    - Redis 7+ with RediSearch module running locally
    - AWS credentials configured (env vars or ~/.aws/credentials)
    - .env file with required configuration (see README.md)
"""

from __future__ import annotations

import redis
import boto3

from core.config import Config
from core.llm import BedrockClaudeLLM
from core.embeddings import TitanEmbedder
from repo.local_task_repo import LocalTaskRepo
from repo.vector_index import ensure_vss_index
from seeds.seed_loader import seed_atomic_tasks


def startup() -> None:
    """Bootstrap the workflow engine."""
    cfg = Config()

    # ── Ensure local directories exist ───────────────────────────────────────
    for subdir in ["atomic_tasks", "workflows", "embeddings"]:
        (cfg.BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # ── Initialise clients ───────────────────────────────────────────────────
    redis_client = redis.Redis(
        host=cfg.REDIS_HOST,
        port=cfg.REDIS_PORT,
        db=cfg.REDIS_DB,
    )
    bedrock_client = boto3.client(
        "bedrock-runtime", region_name=cfg.AWS_REGION
    )

    llm = BedrockClaudeLLM(bedrock_client, cfg)
    embedder = TitanEmbedder(bedrock_client, cfg)

    # ── Ensure VSS index exists in Redis ─────────────────────────────────────
    ensure_vss_index(redis_client, embedding_dim=cfg.EMBEDDING_DIM)
    print("[STARTUP] Redis VSS index ready.")

    # ── Warm Redis cache from local filesystem if cold ───────────────────────
    repo = LocalTaskRepo(redis_client, embedder, cfg)
    repo.warm_cache_from_local()
    print(f"[STARTUP] Warmed cache — {redis_client.scard('task:index')} tasks in index.")

    # ── Seed pre-built tasks from seeds/ if repo is empty ────────────────────
    if redis_client.scard("task:index") == 0:
        count = seed_atomic_tasks(repo, cfg)
        print(f"[STARTUP] Seeded {count} atomic tasks from seeds/.")
    else:
        print("[STARTUP] Tasks already seeded — skipping.")

    print(f"\n[STARTUP] Workflow Engine ready.")
    print(f"  Base directory : {cfg.BASE_DIR}")
    print(f"  Redis          : {cfg.REDIS_HOST}:{cfg.REDIS_PORT}/{cfg.REDIS_DB}")
    print(f"  Bedrock model  : {cfg.BEDROCK_CLAUDE_MODEL}")
    print(f"  Tasks indexed  : {redis_client.scard('task:index')}")
    print()

    # NOTE: REPL / ChatSession is a later phase — this is Phase 1 only.
    # To verify, run:
    #   repo.search_similar_tasks("extract text from pdf")
    #   repo.get_task("extract_text_from_pdf_v1")


if __name__ == "__main__":
    startup()
