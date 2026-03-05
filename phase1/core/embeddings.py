"""
TitanEmbedder — wrapper around Amazon Titan Embeddings V2 via Bedrock.
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


class TitanEmbedder:
    """Callable that returns a float-vector embedding for a given text."""

    def __init__(self, bedrock_client: Any, cfg: "Config") -> None:
        self.client = bedrock_client
        self.model_id = cfg.BEDROCK_EMBED_MODEL

    def __call__(self, text: str) -> list[float]:
        """Embed *text* using Amazon Titan and return a list of floats."""
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        return body["embedding"]
