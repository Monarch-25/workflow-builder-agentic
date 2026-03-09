"""Gap detection helpers for approved orchestrator plans."""

from __future__ import annotations

from .models import GapAnalysis, PlanIssue, ProposedPlan


def detect_gaps(
    plan: ProposedPlan,
    validation_issues: list[PlanIssue] | None = None,
) -> GapAnalysis:
    """Split a plan into repo, adapted, and missing work items."""
    existing_steps = []
    adapted_steps = []
    missing_steps = []
    follow_up_questions = []

    for step in plan.task_list:
        if step.source == "repo":
            existing_steps.append(step)
            continue
        if step.source == "repo_adapted":
            adapted_steps.append(step)
            follow_up_questions.append(
                f"Confirm the adaptation for step {step.step}: {step.gap_notes}"
            )
            continue
        missing_steps.append(step)
        follow_up_questions.append(
            f"Should a new task be created for step {step.step}: {step.name}?"
        )

    return GapAnalysis(
        existing_steps=existing_steps,
        adapted_steps=adapted_steps,
        missing_steps=missing_steps,
        validation_issues=validation_issues or [],
        follow_up_questions=follow_up_questions,
    )

