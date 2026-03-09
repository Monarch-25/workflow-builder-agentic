"""Tests for gap detection and validation helpers."""

from __future__ import annotations

import unittest

from phase2.orchestrator.gap_detector import detect_gaps
from phase2.orchestrator.models import PlanIssue, ProposedPlan, TaskStep


class GapDetectorTests(unittest.TestCase):
    def test_detect_gaps_splits_repo_adapted_and_new_steps(self) -> None:
        plan = ProposedPlan(
            reasoning="Mixed plan",
            task_list=[
                TaskStep(
                    step=1,
                    task_id="upload_file_v1",
                    name="Upload File",
                    description="Upload the file.",
                    source="repo",
                ),
                TaskStep(
                    step=2,
                    task_id="parse_swift_message_v1",
                    name="Parse SWIFT Message",
                    description="Partial SWIFT parser.",
                    source="repo_adapted",
                    gap_notes="Needs MT950 support.",
                ),
                TaskStep(
                    step=3,
                    task_id=None,
                    name="Reconcile MT950 Report",
                    description="Build reconciliation output.",
                    source="new",
                    gap_notes="No MT950 reconciler exists.",
                ),
            ],
        )

        analysis = detect_gaps(
            plan,
            validation_issues=[
                PlanIssue(code="warning", message="Example", severity="warning")
            ],
        )

        self.assertEqual(len(analysis.existing_steps), 1)
        self.assertEqual(len(analysis.adapted_steps), 1)
        self.assertEqual(len(analysis.missing_steps), 1)
        self.assertEqual(len(analysis.validation_issues), 1)
        self.assertEqual(len(analysis.follow_up_questions), 2)


if __name__ == "__main__":
    unittest.main()

