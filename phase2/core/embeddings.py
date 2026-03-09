"""Phase 2 embedding wrapper.

This mirrors the Phase 1 Titan embedder behavior without depending on the
``phase1.core`` package initialization path.
"""

from __future__ import annotations

import json
from typing import Any

from .config import Config


class TitanEmbedder:
    """Callable that returns a Titan embedding vector for a text input."""

    def __init__(self, bedrock_client: Any, cfg: Config) -> None:
        self.client = bedrock_client
        self.model_id = cfg.BEDROCK_EMBED_MODEL

    def __call__(self, text: str) -> list[float]:
        """Embed text using Amazon Titan and return the vector."""
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        body = response["body"]
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        payload = json.loads(body)
        return payload["embedding"]
