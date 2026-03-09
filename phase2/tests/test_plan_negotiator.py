"""Tests for multi-turn natural-language plan negotiation."""

from __future__ import annotations

import unittest

from phase2.core import Config
from phase2.orchestrator.models import OrchestrationTurn, ProposedPlan, TaskStep
from phase2.orchestrator.plan_negotiator import PlanNegotiator, PlanSession
from phase2.orchestrator.intent_parser import IntentParser
from phase2.tests.helpers import InMemoryTaskRepo, load_seed_tasks


def build_review_turn() -> OrchestrationTurn:
    return OrchestrationTurn(
        state="awaiting_user_confirmation",
        user_request="extract all working URLs from a PDF",
        plan=ProposedPlan(
            reasoning="Base plan for URL extraction.",
            task_list=[
                TaskStep(
                    step=1,
                    task_id="upload_file_v1",
                    name="Upload File",
                    description="Normalize the incoming file path.",
                    source="repo",
                    input_bindings={"file_path": "$user:file_path"},
                ),
                TaskStep(
                    step=2,
                    task_id="extract_text_from_pdf_v1",
                    name="Extract Text from PDF",
                    description="Extract PDF text.",
                    source="repo",
                    input_bindings={"file_path": "normalized_path"},
                ),
                TaskStep(
                    step=3,
                    task_id="extract_urls_from_text_v1",
                    name="Extract URLs from Text",
                    description="Extract candidate URLs.",
                    source="repo",
                    input_bindings={"raw_text": "raw_text"},
                ),
                TaskStep(
                    step=4,
                    task_id="check_url_liveness_v1",
                    name="Check URL Liveness",
                    description="Verify which URLs are reachable.",
                    source="repo",
                    input_bindings={"urls": "urls", "timeout_sec": "$const:10"},
                ),
                TaskStep(
                    step=5,
                    task_id="return_output_v1",
                    name="Return Output",
                    description="Show the final result.",
                    source="repo",
                    input_bindings={"result": "live_urls", "label": "$const:Live URLs"},
                ),
            ],
        ),
    )


class PlanNegotiatorTests(unittest.TestCase):
    def setUp(self) -> None:
        tasks = load_seed_tasks(
            "upload_file_v1",
            "extract_text_from_pdf_v1",
            "extract_urls_from_text_v1",
            "check_url_liveness_v1",
            "return_output_v1",
            "log_error_v1",
            "deduplicate_list_v1",
        )
        repo = InMemoryTaskRepo(tasks)
        parser = IntentParser(repo, cfg=Config())
        self.negotiator = PlanNegotiator(parser)

    def test_multi_turn_plan_negotiation(self) -> None:
        session = PlanSession(
            user_request="extract all working URLs from a PDF",
            current_turn=build_review_turn(),
        )

        response = self.negotiator.handle_feedback(
            session,
            "swap 3 and 4",
        )
        self.assertIn("Reply `yes` to confirm", response.message)
        self.assertIsNotNone(response.session.pending_confirmation)

        response = self.negotiator.handle_feedback(session, "yes")
        self.assertEqual(response.turn.plan.task_list[2].name, "Check URL Liveness")
        self.assertEqual(response.turn.plan.task_list[3].name, "Extract URLs from Text")

        response = self.negotiator.handle_feedback(
            session,
            "remove the last step",
        )
        self.assertIsNotNone(response.session.pending_confirmation)
        response = self.negotiator.handle_feedback(session, "yes")
        self.assertEqual(len(response.turn.plan.task_list), 4)

        response = self.negotiator.handle_feedback(
            session,
            "add a deduplicate list step after step 3",
        )
        response = self.negotiator.handle_feedback(session, "yes")
        self.assertTrue(
            any(step.task_id == "deduplicate_list_v1" for step in response.turn.plan.task_list)
        )

        previous_state = response.turn.state
        response = self.negotiator.handle_feedback(
            session,
            "what does the deduplicate list step do?",
        )
        self.assertEqual(response.turn.state, previous_state)
        self.assertIn("Deduplicate List", response.message)

        response = self.negotiator.handle_feedback(session, "looks good")
        self.assertEqual(response.turn.state, "approved")


if __name__ == "__main__":
    unittest.main()
