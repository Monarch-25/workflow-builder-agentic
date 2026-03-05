"""
LocalTaskRepo — CRUD + semantic search for atomic tasks.

Storage strategy:
  • **Local filesystem** (source of truth) — each task lives under
    ``~/.workflow_engine/atomic_tasks/<task_id>/`` with ``script.py``
    and ``metadata.json``.
  • **Redis** (hot cache + VSS) — metadata is cached with a TTL;
    embeddings are stored in a RediSearch HNSW index for KNN search.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from redis.commands.search.query import Query

from .schema import AtomicTask

if TYPE_CHECKING:
    from redis import Redis
    from core.config import Config
    from core.embeddings import TitanEmbedder


class LocalTaskRepo:
    """Manages atomic tasks on local disk + Redis cache/VSS."""

    def __init__(
        self,
        redis_client: "Redis",
        embedder: "TitanEmbedder",
        cfg: "Config",
    ) -> None:
        self.redis = redis_client
        self.embed = embedder
        self.cfg = cfg
        self.base: Path = cfg.BASE_DIR / "atomic_tasks"
        self.base.mkdir(parents=True, exist_ok=True)

    # ── write ────────────────────────────────────────────────────────────────

    def upsert_task(self, task: AtomicTask, script: str) -> None:
        """Persist *task* to local disk **and** Redis (metadata + VSS)."""
        # Local filesystem (portable metadata stores relative script path)
        task.script_path = "script.py"
        task_dir = self.base / task.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / task.script_path).write_text(script)
        (task_dir / "metadata.json").write_text(task.model_dump_json(indent=2))

        # Generate embedding
        embedding = self.embed(task.description)
        task.embedding = embedding

        # Redis VSS hash
        self.redis.hset(
            f"task:vec:{task.task_id}",
            mapping={
                "task_id": task.task_id,
                "name": task.name,
                "description": task.description,
                "embedding": np.array(embedding, dtype=np.float32).tobytes(),
            },
        )

        # Redis metadata cache (with TTL)
        self.redis.sadd("task:index", task.task_id)
        self.redis.setex(
            f"task:meta:{task.task_id}",
            self.cfg.TASK_CACHE_TTL_SEC,
            task.model_dump_json(),
        )

    # ── read ─────────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> AtomicTask:
        """
        Retrieve task metadata — Redis cache first, local fallback.
        """
        cached = self.redis.get(f"task:meta:{task_id}")
        if cached:
            return AtomicTask.model_validate_json(cached)

        # Fallback to local filesystem
        meta_path = self.base / task_id / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"Task '{task_id}' not found in repo or on disk."
            )
        task = AtomicTask(**json.loads(meta_path.read_text()))

        # Re-populate cache
        self.redis.setex(
            f"task:meta:{task_id}",
            self.cfg.TASK_CACHE_TTL_SEC,
            task.model_dump_json(),
        )
        return task

    def get_script(self, task_id: str) -> str:
        """Return the Python source of the task's ``script.py``."""
        task = self.get_task(task_id)
        task_dir = (self.base / task_id).resolve()
        script_rel_path = Path(task.script_path)
        if script_rel_path.is_absolute():
            raise ValueError(
                f"Task '{task_id}' has absolute script_path; expected relative path."
            )
        script_path = (task_dir / script_rel_path).resolve()
        try:
            script_path.relative_to(task_dir)
        except ValueError as exc:
            raise ValueError(
                f"Task '{task_id}' script_path escapes task directory: {task.script_path}"
            ) from exc
        if not script_path.exists():
            raise FileNotFoundError(
                f"Script for task '{task_id}' not found at {script_path}."
            )
        return script_path.read_text()

    def delete_task(self, task_id: str) -> None:
        """Delete task from local filesystem and Redis cache/index."""
        task_dir = self.base / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)

        self.redis.delete(f"task:meta:{task_id}")
        self.redis.delete(f"task:vec:{task_id}")
        self.redis.srem("task:index", task_id)

    # ── search ───────────────────────────────────────────────────────────────

    def search_similar_tasks(
        self, query: str, top_k: int | None = None
    ) -> list[AtomicTask]:
        """
        Semantic KNN search via Redis VSS (HNSW / COSINE).

        Returns up to *top_k* tasks ranked by embedding similarity.
        """
        k = top_k or self.cfg.VSS_TOP_K
        q_vec = np.array(self.embed(query), dtype=np.float32).tobytes()

        results = (
            self.redis.ft("task_vss_idx")
            .search(
                Query(f"*=>[KNN {k} @embedding $vec AS score]")
                .sort_by("score")
                .return_fields("task_id", "name", "description", "score")
                .dialect(2),
                query_params={"vec": q_vec},
            )
        )
        return [self.get_task(doc.task_id) for doc in results.docs]

    # ── list ─────────────────────────────────────────────────────────────────

    def list_all_tasks(self) -> list[str]:
        """Return all registered task IDs."""
        task_ids = self.redis.smembers("task:index")
        return [t.decode() if isinstance(t, bytes) else str(t) for t in task_ids]

    # ── warm cache ───────────────────────────────────────────────────────────

    def warm_cache_from_local(self) -> None:
        """
        Re-index **all** local tasks into Redis when the cache is cold
        (e.g. fresh Redis instance or after a flush).
        """
        if self.redis.scard("task:index") > 0:
            return  # cache is already warm

        for task_dir in sorted(self.base.iterdir()):
            if not task_dir.is_dir():
                continue
            meta_path = task_dir / "metadata.json"
            script_path = task_dir / "script.py"
            if meta_path.exists() and script_path.exists():
                task = AtomicTask(**json.loads(meta_path.read_text()))
                script = script_path.read_text()
                self.upsert_task(task, script)
