"""Bedrock wrapper for Phase 2 orchestration.

The orchestrator defaults to ``InvokeModel`` because Bedrock's native Tool
Search support is exposed there rather than on the ``Converse`` API.
"""

from __future__ import annotations

import json
import logging
from typing import Any

if False:  # pragma: no cover
    from .config import Config

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "bedrock-2023-05-31"


class BedrockClaudeLLM:
    """Thin Bedrock client with both ``invoke_model`` and ``converse`` paths."""

    def __init__(self, bedrock_client: Any, cfg: "Config") -> None:
        self.client = bedrock_client
        self.model_id = cfg.BEDROCK_CLAUDE_MODEL
        self.beta = cfg.BEDROCK_ADVANCED_TOOL_BETA
        self.log_requests = cfg.LOG_LLM_REQUESTS
        self.default_transport = cfg.ORCHESTRATOR_DEFAULT_TRANSPORT

    def build_invoke_body(
        self,
        *,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        tool_choice: dict[str, Any] | None = None,
        enable_advanced_tools: bool = True,
        prompt_cache: bool = False,
        extra_body_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the Anthropic Messages payload used with Bedrock invoke."""
        body: dict[str, Any] = {
            "anthropic_version": ANTHROPIC_VERSION,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if tools:
            body["tools"] = tools

        if tool_choice:
            body["tool_choice"] = tool_choice

        if enable_advanced_tools:
            body["anthropic_beta"] = [self.beta]

        if prompt_cache:
            body["cache_control"] = {"type": "ephemeral"}

        if extra_body_fields:
            body.update(extra_body_fields)

        return body

    def build_invoke_request(
        self,
        *,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        tool_choice: dict[str, Any] | None = None,
        enable_advanced_tools: bool = True,
        prompt_cache: bool = False,
        extra_body_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the full boto3 ``invoke_model`` request."""
        body = self.build_invoke_body(
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            enable_advanced_tools=enable_advanced_tools,
            prompt_cache=prompt_cache,
            extra_body_fields=extra_body_fields,
        )
        request = {
            "modelId": self.model_id,
            "body": json.dumps(body),
            "contentType": "application/json",
            "accept": "application/json",
        }
        return request

    def build_orchestrator_request(
        self,
        *,
        user_text: str,
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
        prompt_cache: bool = False,
    ) -> dict[str, Any]:
        """Build the default orchestration request using ``InvokeModel``."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
            }
        ]
        return self.build_invoke_request(
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
            tool_choice={"type": "auto"},
            enable_advanced_tools=True,
            prompt_cache=prompt_cache,
        )

    def invoke_orchestrator(
        self,
        *,
        user_text: str,
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
        prompt_cache: bool = False,
    ) -> dict[str, Any]:
        """Call Bedrock ``InvokeModel`` for orchestration."""
        request = self.build_orchestrator_request(
            user_text=user_text,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
            prompt_cache=prompt_cache,
        )
        if self.log_requests:
            logger.info("Bedrock invoke_model request payload: %s", request["body"])
        response = self.client.invoke_model(**request)
        return self.normalize_invoke_response(response)

    def normalize_invoke_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Bedrock invoke response into a plain dict."""
        body = response.get("body", response)
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if isinstance(body, str):
            return json.loads(body)
        if isinstance(body, dict):
            return body
        raise TypeError(f"Unsupported Bedrock response body type: {type(body)!r}")

    def build_converse_request(
        self,
        *,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False,
    ) -> dict[str, Any]:
        """Build a Bedrock ``converse`` request for compatibility paths."""
        request: dict[str, Any] = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if tools:
            request["toolConfig"] = {"tools": tools}
        if enable_advanced_tools:
            request["additionalModelRequestFields"] = {
                "anthropic_beta": [self.beta]
            }
        return request

    def converse(
        self,
        *,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False,
    ) -> dict[str, Any]:
        """Compatibility wrapper for existing ``Converse``-based flows."""
        request = self.build_converse_request(
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
            enable_advanced_tools=enable_advanced_tools,
        )
        if self.log_requests:
            logger.info("Bedrock converse request payload: %s", json.dumps(request))
        return self.client.converse(**request)

    def build_converse_structured_request(
        self,
        *,
        messages: list[dict],
        system: str,
        output_schema: type,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False,
        schema_name: str = "structured_output",
        schema_description: str = "Return JSON matching the requested schema.",
    ) -> dict[str, Any]:
        """Build a ``Converse`` request with Bedrock structured output enabled."""
        request = self.build_converse_request(
            messages=messages,
            system=system,
            tools=None,
            max_tokens=max_tokens,
            enable_advanced_tools=enable_advanced_tools,
        )
        request["outputConfig"] = {
            "textFormat": {
                "type": "json_schema",
                "structure": {
                    "jsonSchema": {
                        "name": schema_name,
                        "description": schema_description,
                        "schema": json.dumps(output_schema.model_json_schema()),
                    }
                },
            }
        }
        return request

    def converse_structured(
        self,
        *,
        system: str,
        messages: list[dict],
        output_schema: type,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False,
        schema_name: str = "structured_output",
        schema_description: str = "Return JSON matching the requested schema.",
    ) -> Any:
        """Run a structured ``Converse`` call and validate the JSON response."""
        request = self.build_converse_structured_request(
            messages=messages,
            system=system,
            output_schema=output_schema,
            max_tokens=max_tokens,
            enable_advanced_tools=enable_advanced_tools,
            schema_name=schema_name,
            schema_description=schema_description,
        )
        if self.log_requests:
            logger.info(
                "Bedrock converse structured request payload: %s",
                json.dumps(request),
            )
        response = self.client.converse(**request)
        content = response.get("output", {}).get("message", {}).get("content", [])
        for block in content:
            text = block.get("text")
            if text:
                return output_schema.model_validate_json(text)
        raise ValueError("Structured Converse response did not include a text block.")
