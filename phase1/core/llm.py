"""
BedrockClaudeLLM — wrapper around Bedrock converse API.

Supports:
  • Standard converse calls
  • Advanced tool use beta header injection
  • Structured output via forced tool use (schema-constrained JSON)
"""

from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


class BedrockClaudeLLM:
    """Thin wrapper around ``bedrock-runtime`` converse API."""

    def __init__(self, bedrock_client: Any, cfg: "Config") -> None:
        self.client = bedrock_client
        self.model_id = cfg.BEDROCK_CLAUDE_MODEL
        self.beta = cfg.BEDROCK_ADVANCED_TOOL_BETA
        self.log_requests = cfg.LOG_LLM_REQUESTS

    # ── core call ────────────────────────────────────────────────────────────

    def converse(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False,
    ) -> dict:
        """
        Core Bedrock converse call.

        When *enable_advanced_tools* is ``True`` the advanced tool-use beta
        header is injected via ``additionalModelRequestFields``.
        """
        request: dict[str, Any] = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }

        if tools:
            request["toolConfig"] = {"tools": tools}

        if enable_advanced_tools:
            # Beta header passed through Bedrock's converse API
            request["additionalModelRequestFields"] = {
                "anthropic_beta": [self.beta]
            }

        if self.log_requests:
            logger.info(
                "Bedrock converse request payload: %s",
                json.dumps(request, default=str),
            )

        return self.client.converse(**request)

    # ── structured output ────────────────────────────────────────────────────

    def invoke_structured(
        self,
        system: str,
        messages: list[dict],
        output_schema: type,
        enable_advanced_tools: bool = False,
    ) -> Any:
        """
        Force JSON output matching a Pydantic schema using tool use.

        A synthetic ``structured_output`` tool whose *inputSchema* mirrors
        the Pydantic model is declared; the model is compelled to call it,
        producing validated structured output.
        """
        schema_tool = [
            {
                "toolSpec": {
                    "name": "structured_output",
                    "description": (
                        "Return structured data exactly matching the schema."
                    ),
                    "inputSchema": {
                        "json": output_schema.model_json_schema()
                    },
                }
            }
        ]

        response = self.converse(
            messages=messages,
            system=system,
            tools=schema_tool,
            enable_advanced_tools=enable_advanced_tools,
        )

        for block in response["output"]["message"]["content"]:
            tool_use = block.get("toolUse", {})
            if tool_use.get("name") == "structured_output":
                return output_schema.model_validate(tool_use["input"])

        raise ValueError(
            "Model did not return expected structured output via "
            "'structured_output' tool."
        )
