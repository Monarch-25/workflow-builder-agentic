"""Tests for the Phase 2 Bedrock transport wrapper."""

from __future__ import annotations

import json
import unittest

from phase2.core.config import Config
from phase2.core.llm import BedrockClaudeLLM


class DummyBedrockClient:
    """Tiny stub used for request-shape tests."""

    def invoke_model(self, **_: object) -> dict[str, object]:
        return {"body": json.dumps({"content": []})}


class LLMTests(unittest.TestCase):
    def test_orchestrator_request_defaults_to_invoke_model_shape(self) -> None:
        llm = BedrockClaudeLLM(DummyBedrockClient(), Config())
        request = llm.build_orchestrator_request(
            user_text="extract all working URLs from a PDF",
            system="system prompt",
            tools=[{"type": "tool_search_tool_regex_20251119", "name": "tool_search"}],
        )

        self.assertEqual(request["contentType"], "application/json")
        payload = json.loads(request["body"])
        self.assertEqual(payload["tool_choice"]["type"], "auto")
        self.assertIn("anthropic_beta", payload)
        self.assertEqual(payload["messages"][0]["role"], "user")


if __name__ == "__main__":
    unittest.main()

