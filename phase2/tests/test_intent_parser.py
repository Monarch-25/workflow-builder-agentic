"""Tests for the clarification-first intent parser."""

from __future__ import annotations

import unittest

from phase2.core.config import Config
from phase2.core.llm import BedrockClaudeLLM
from phase2.orchestrator.intent_parser import IntentParser
from phase2.orchestrator.validators import validate_plan
from phase2.tests.helpers import InMemoryTaskRepo, load_seed_tasks


class RecordingClient:
    """Stub Bedrock client that records the last invoke request."""

    def __init__(self) -> None:
        self.last_request: dict[str, object] | None = None

    def invoke_model(self, **kwargs: object) -> dict[str, object]:
        self.last_request = kwargs
        return {"body": "{\"content\": []}"}


class SparseSearchRepo(InMemoryTaskRepo):
    """Repo that forces the parser to use multiple retrieval queries."""

    def __init__(self, tasks) -> None:
        super().__init__(tasks)
        self.calls: list[str] = []

    def search_similar_tasks(self, query: str, top_k: int | None = None):
        self.calls.append(query)
        if len(self.calls) == 1:
            return super().search_similar_tasks("pdf", top_k=1)
        return super().search_similar_tasks(query, top_k=top_k)


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = load_seed_tasks(
            "upload_file_v1",
            "extract_text_from_pdf_v1",
            "extract_urls_from_text_v1",
            "check_url_liveness_v1",
            "return_output_v1",
            "log_error_v1",
            "parse_swift_message_v1",
        )

    def test_pdf_url_request_returns_all_repo_plan(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        parser = IntentParser(repo, cfg=Config())

        turn = parser.parse("extract all working URLs from a PDF")

        self.assertEqual(turn.state, "awaiting_user_confirmation")
        self.assertEqual(
            [step.task_id for step in turn.plan.task_list],
            [
                "upload_file_v1",
                "extract_text_from_pdf_v1",
                "extract_urls_from_text_v1",
                "check_url_liveness_v1",
            ],
        )
        self.assertEqual({step.source for step in turn.plan.task_list}, {"repo"})
        self.assertEqual(turn.issues, [])

    def test_ambiguous_request_asks_for_clarification(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        parser = IntentParser(repo, cfg=Config())

        turn = parser.parse("process report")

        self.assertEqual(turn.state, "needs_clarification")
        self.assertGreaterEqual(len(turn.clarification_set.questions), 1)

    def test_multi_search_iteration_collects_more_than_one_query(self) -> None:
        repo = SparseSearchRepo(self.tasks)
        parser = IntentParser(repo, cfg=Config())

        turn = parser.parse("extract all working URLs from a PDF")

        self.assertEqual(turn.state, "awaiting_user_confirmation")
        self.assertGreaterEqual(len(turn.search_queries), 2)
        self.assertGreaterEqual(len(repo.calls), 2)

    def test_validation_detects_missing_bindings(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        parser = IntentParser(repo, cfg=Config())
        turn = parser.parse("extract all working URLs from a PDF")
        broken_plan = turn.plan.model_copy(deep=True)
        broken_plan.task_list[1].input_bindings = {}

        issues = validate_plan(
            broken_plan,
            repo,
            user_inputs={},
        )

        self.assertTrue(any(issue.code == "missing_input" for issue in issues))

    def test_prepared_request_uses_invoke_model_default(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        client = RecordingClient()
        llm = BedrockClaudeLLM(client, Config())
        parser = IntentParser(repo, cfg=Config(), llm=llm)

        request = parser.prepare_llm_request("extract all working URLs from a PDF")

        self.assertIsNotNone(request)
        self.assertEqual(request["contentType"], "application/json")
        self.assertEqual(request["accept"], "application/json")


if __name__ == "__main__":
    unittest.main()
