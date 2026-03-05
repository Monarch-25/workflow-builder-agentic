"""
Redis VSS index setup — uses redis-py's built-in RediSearch module.

Creates a HNSW vector index over task embeddings so that
``LocalTaskRepo.search_similar_tasks()`` can perform fast KNN queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from redis.commands.search.field import TextField, VectorField
try:
    from redis.commands.search.index_definition import (
        IndexDefinition,
        IndexType,
    )
except ImportError:  # pragma: no cover - compatibility for older redis-py
    from redis.commands.search.indexDefinition import (  # type: ignore
        IndexDefinition,
        IndexType,
    )

if TYPE_CHECKING:
    from redis import Redis


def ensure_vss_index(redis_client: "Redis", embedding_dim: int = 1536) -> None:
    """
    Idempotently create the ``task_vss_idx`` RediSearch index.

    Uses redis-py's built-in search module — no external HNSW library
    is required; RediSearch natively supports HNSW vector indexes.
    """
    index_name = "task_vss_idx"

    try:
        redis_client.ft(index_name).info()
        return  # index already exists
    except Exception:
        pass  # index does not exist yet — create it

    schema = (
        # HASH index fields must use plain field names (not JSON paths).
        TextField("task_id"),
        TextField("name"),
        TextField("description"),
        VectorField(
            "embedding",
            algorithm="HNSW",
            attributes={
                "TYPE": "FLOAT32",
                "DIM": embedding_dim,
                "DISTANCE_METRIC": "COSINE",
                "M": 16,
                "EF_CONSTRUCTION": 200,
            },
        ),
    )

    redis_client.ft(index_name).create_index(
        schema,
        definition=IndexDefinition(
            prefix=["task:vec:"],
            index_type=IndexType.HASH,
        ),
    )
