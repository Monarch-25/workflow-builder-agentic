"""Tests for Phase 2 startup and integration helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from phase2.core.config import Config
from phase2.startup import (
    bootstrap_runtime,
    parse_answer_pairs,
    render_turn,
    run_orchestration,
    seed_repo_from_phase1_seeds,
)
from phase2.tests.helpers import InMemoryTaskRepo, load_seed_tasks


class FakeEmbedder:
    """Lightweight embedder stub for runtime construction tests."""

    def __call__(self, text: str) -> list[float]:
        return [float(len(text))]


class FakeBedrockClient:
    """Bedrock stub matching the shape expected by the wrappers."""

    def invoke_model(self, **_: object) -> dict[str, object]:
        return {"body": "{\"embedding\": [1.0], \"content\": []}"}


class FakeRedisClient:
    """Tiny Redis stub for injected-runtime tests."""

    def scard(self, _: str) -> int:
        return 1


class RecordingRepo:
    """Repo stub used to verify seed loading."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def upsert_task(self, task, script: str) -> None:
        self.calls.append((task.task_id, script))


class StartupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = load_seed_tasks(
            "upload_file_v1",
            "extract_text_from_pdf_v1",
            "extract_urls_from_text_v1",
            "check_url_liveness_v1",
            "return_output_v1",
            "log_error_v1",
        )

    def test_parse_answer_pairs(self) -> None:
        answers = parse_answer_pairs(
            ["input_artifact=pdf", "desired_output=live urls only"]
        )
        self.assertEqual(
            answers,
            {
                "input_artifact": "pdf",
                "desired_output": "live urls only",
            },
        )

    def test_seed_repo_from_phase1_seeds_loads_tasks(self) -> None:
        repo = RecordingRepo()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "atomic_tasks"
            task_dir = base / "example_task_v1"
            task_dir.mkdir(parents=True)
            (task_dir / "metadata.json").write_text(
                """
                {
                  "task_id": "example_task_v1",
                  "name": "Example Task",
                  "description": "Example description",
                  "input_schema": {"value": "str"},
                  "output_schema": {"result": "str"},
                  "script_path": "script.py",
                  "dependencies": [],
                  "tags": ["example"],
                  "author": "system",
                  "created_at": "2025-01-01T00:00:00",
                  "verified": true,
                  "version": 1,
                  "usage_count": 0,
                  "usage_examples": [{"value": "x"}]
                }
                """.strip()
            )
            (task_dir / "script.py").write_text("print('ok')\n")

            count = seed_repo_from_phase1_seeds(repo, seeds_dir=base)

        self.assertEqual(count, 1)
        self.assertEqual(repo.calls[0][0], "example_task_v1")

    def test_bootstrap_runtime_with_injected_repo(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        runtime = bootstrap_runtime(
            Config(),
            redis_client=FakeRedisClient(),
            bedrock_client=FakeBedrockClient(),
            repo=repo,
        )

        self.assertIs(runtime.repo, repo)
        self.assertEqual(runtime.parser.repo, repo)
        self.assertEqual(runtime.negotiator.parser, runtime.parser)

    def test_run_orchestration_returns_renderable_turn(self) -> None:
        repo = InMemoryTaskRepo(self.tasks)
        runtime = bootstrap_runtime(
            Config(),
            redis_client=FakeRedisClient(),
            bedrock_client=FakeBedrockClient(),
            repo=repo,
        )

        turn = run_orchestration(
            "extract all working URLs from a PDF",
            runtime=runtime,
        )

        self.assertEqual(turn.state, "awaiting_user_confirmation")
        rendered = render_turn(turn)
        self.assertIn("awaiting_user_confirmation", rendered)


if __name__ == "__main__":
    unittest.main()
