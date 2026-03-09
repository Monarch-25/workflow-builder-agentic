"""Tests for the Phase 3 intent inference node."""

from __future__ import annotations

import unittest

from phase2.core.intent_infer import IntentInferenceNode, IntentType


class IntentInferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.node = IntentInferenceNode()
        self.current_state = {
            "plan": [
                {
                    "step": 1,
                    "name": "Upload File",
                    "description": "Normalize the incoming file path.",
                },
                {
                    "step": 2,
                    "name": "Extract URLs",
                    "description": "Extract URLs from the raw text.",
                },
                {
                    "step": 3,
                    "name": "Deduplicate List",
                    "description": "Remove duplicate URLs.",
                },
                {
                    "step": 4,
                    "name": "URL Check",
                    "description": "Check URL liveness.",
                },
                {
                    "step": 5,
                    "name": "Return Output",
                    "description": "Render the final result.",
                },
            ]
        }

    def test_modify_plan_extracts_multiple_edits(self) -> None:
        intent = self.node.infer(
            "yeah looks good but move the URL check before dedup and drop the last step",
            "plan_review",
            self.current_state,
            [],
        )

        self.assertEqual(intent.intent_type, IntentType.MODIFY_PLAN)
        self.assertEqual(len(intent.payload["edits"]), 2)
        self.assertEqual(intent.payload["edits"][0]["action"], "reorder")
        self.assertEqual(intent.payload["edits"][0]["from_step"], 4)
        self.assertEqual(intent.payload["edits"][0]["to_before_step"], 3)
        self.assertEqual(intent.payload["edits"][1], {"action": "remove", "step": 5})

    def test_ambiguous_modify_stays_low_confidence(self) -> None:
        intent = self.node.infer(
            "maybe change it?",
            "plan_review",
            self.current_state,
            [],
        )

        self.assertEqual(intent.intent_type, IntentType.MODIFY_PLAN)
        self.assertLess(intent.confidence, 0.85)

    def test_question_routes_to_question_intent(self) -> None:
        intent = self.node.infer(
            "what does the dedup step actually do?",
            "plan_review",
            self.current_state,
            [],
        )

        self.assertEqual(intent.intent_type, IntentType.QUESTION)
        self.assertEqual(intent.payload["step"], 3)

    def test_bedrock_path_is_default_when_llm_is_available(self) -> None:
        class StubLLM:
            def converse_structured(self, **_: object):
                from phase2.core.intent_infer import InferredIntent

                return InferredIntent(
                    intent_type=IntentType.APPROVE,
                    confidence=0.98,
                    payload={},
                    user_message_rephrased="You approve the plan.",
                )

        node = IntentInferenceNode(StubLLM())
        intent = node.infer("looks good", "plan_review", self.current_state, [])

        self.assertEqual(intent.intent_type, IntentType.APPROVE)
        self.assertEqual(intent.confidence, 0.98)

    def test_falls_back_to_heuristics_when_bedrock_path_fails(self) -> None:
        class FailingLLM:
            def converse_structured(self, **_: object):
                raise RuntimeError("bedrock unavailable")

        node = IntentInferenceNode(FailingLLM())
        intent = node.infer(
            "move the URL check before dedup",
            "plan_review",
            self.current_state,
            [],
        )

        self.assertEqual(intent.intent_type, IntentType.MODIFY_PLAN)
        self.assertGreaterEqual(intent.confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
