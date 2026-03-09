"""Deterministic validation for orchestrator draft plans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from phase1.repo.schema import AtomicTask

from .models import PlanIssue, ProposedPlan, TaskStep


class TaskRepoProtocol(Protocol):
    """Minimal repo surface needed by plan validators."""

    def get_task(self, task_id: str) -> AtomicTask:
        ...


def _is_user_binding(binding: str) -> bool:
    return binding.startswith("$user:")


def _is_const_binding(binding: str) -> bool:
    return binding.startswith("$const:")


def types_compatible(source_type: str, target_type: str) -> bool:
    if source_type == target_type:
        return True
    aliases = {
        "dict[str, any]": "dict",
        "list[dict[str, any]]": "list[dict]",
        "list[object]": "list",
    }
    source_normalized = aliases.get(source_type.lower(), source_type.lower())
    target_normalized = aliases.get(target_type.lower(), target_type.lower())
    if source_normalized == target_normalized:
        return True
    if source_normalized.startswith("list[") and target_normalized == "list":
        return True
    if source_normalized == "dict" and target_normalized.startswith("dict"):
        return True
    return False


def _validate_numbering(plan: ProposedPlan) -> list[PlanIssue]:
    issues: list[PlanIssue] = []
    expected = 1
    for step in sorted(plan.task_list, key=lambda item: item.step):
        if step.step != expected:
            issues.append(
                PlanIssue(
                    code="step_number_gap",
                    message=(
                        f"Expected step number {expected}, found {step.step}."
                    ),
                    step=step.step,
                )
            )
        expected += 1
    return issues


def _get_schema(
    step: TaskStep,
    repo: TaskRepoProtocol,
) -> tuple[dict[str, str], dict[str, str]] | None:
    if not step.task_id:
        return None
    task = repo.get_task(step.task_id)
    return task.input_schema, task.output_schema


def validate_plan(
    plan: ProposedPlan,
    repo: TaskRepoProtocol,
    user_inputs: Mapping[str, str] | None = None,
) -> list[PlanIssue]:
    """Validate the plan structure and step-to-step data compatibility."""
    issues = _validate_numbering(plan)
    available_fields = dict(user_inputs or {})
    last_step_number = 0

    for step in sorted(plan.task_list, key=lambda item: item.step):
        last_step_number = step.step
        if step.source not in {"repo", "repo_adapted", "new"}:
            issues.append(
                PlanIssue(
                    code="invalid_source",
                    message=f"Invalid source '{step.source}' for step {step.step}.",
                    step=step.step,
                )
            )
            continue

        if step.source in {"repo", "repo_adapted"}:
            if not step.task_id:
                issues.append(
                    PlanIssue(
                        code="missing_task_id",
                        message="Repo-backed steps must include a task_id.",
                        step=step.step,
                    )
                )
                continue
            try:
                schema = _get_schema(step, repo)
            except FileNotFoundError:
                schema = None
            if schema is None:
                issues.append(
                    PlanIssue(
                        code="unknown_task_id",
                        message=f"Task '{step.task_id}' was not found in the repo.",
                        step=step.step,
                    )
                )
                continue
            input_schema, output_schema = schema
            if step.source == "repo_adapted" and not step.gap_notes:
                issues.append(
                    PlanIssue(
                        code="missing_adaptation_note",
                        message="repo_adapted steps must explain the adaptation.",
                        step=step.step,
                    )
                )
            for input_name, input_type in input_schema.items():
                binding = step.input_bindings.get(input_name)
                if binding:
                    if _is_user_binding(binding) or _is_const_binding(binding):
                        continue
                    if binding not in available_fields:
                        issues.append(
                            PlanIssue(
                                code="missing_binding_source",
                                message=(
                                    f"Input '{input_name}' binds to unknown field "
                                    f"'{binding}'."
                                ),
                                step=step.step,
                            )
                        )
                        continue
                    if not types_compatible(available_fields[binding], input_type):
                        issues.append(
                            PlanIssue(
                                code="binding_type_mismatch",
                                message=(
                                    f"Input '{input_name}' expects {input_type} but "
                                    f"binding '{binding}' provides "
                                    f"{available_fields[binding]}."
                                ),
                                step=step.step,
                            )
                        )
                    continue
                if input_name in available_fields and types_compatible(
                    available_fields[input_name], input_type
                ):
                    continue
                issues.append(
                    PlanIssue(
                        code="missing_input",
                        message=(
                            f"Input '{input_name}' for step {step.step} is not "
                            "satisfied by upstream outputs or explicit bindings."
                        ),
                        step=step.step,
                    )
                )
            available_fields.update(output_schema)
            continue

        if step.source == "new" and not step.gap_notes:
            issues.append(
                PlanIssue(
                    code="missing_gap_note",
                    message="New steps must explain the repo gap.",
                    step=step.step,
                )
            )

    if not plan.task_list and last_step_number == 0:
        issues.append(
            PlanIssue(
                code="empty_plan",
                message="The proposed plan contains no steps.",
            )
        )
    return issues
