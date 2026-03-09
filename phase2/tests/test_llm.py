"""Tests for the Phase 2 Bedrock transport wrapper."""

from __future__ import annotations

import json
import unittest

from phase2.core.config import Config
from phase2.core.intent_infer import InferredIntent, IntentType
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

    def test_converse_structured_request_uses_json_schema_output(self) -> None:
        llm = BedrockClaudeLLM(DummyBedrockClient(), Config())
        request = llm.build_converse_structured_request(
            messages=[{"role": "user", "content": [{"text": "hello"}]}],
            system="system prompt",
            output_schema=InferredIntent,
            schema_name="inferred_intent",
        )

        self.assertIn("outputConfig", request)
        output_config = request["outputConfig"]["textFormat"]
        self.assertEqual(output_config["type"], "json_schema")
        self.assertEqual(
            output_config["structure"]["jsonSchema"]["name"],
            "inferred_intent",
        )

    def test_converse_structured_parses_json_response(self) -> None:
        class StructuredClient:
            def converse(self, **_: object) -> dict[str, object]:
                return {
                    "output": {
                        "message": {
                            "content": [
                                {
                                    "text": json.dumps(
                                        {
                                            "intent_type": IntentType.APPROVE.value,
                                            "confidence": 0.99,
                                            "payload": {},
                                            "user_message_rephrased": "You approve the plan.",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                }

        llm = BedrockClaudeLLM(StructuredClient(), Config())
        intent = llm.converse_structured(
            system="system prompt",
            messages=[{"role": "user", "content": [{"text": "approve"}]}],
            output_schema=InferredIntent,
            schema_name="inferred_intent",
        )

        self.assertEqual(intent.intent_type, IntentType.APPROVE)
        self.assertEqual(intent.confidence, 0.99)


if __name__ == "__main__":
    unittest.main()
