"""Pydantic models used by the Phase 2 orchestrator."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["repo", "repo_adapted", "new"]
TurnState = Literal[
    "needs_clarification",
    "searching",
    "draft_plan_ready",
    "validation_failed",
    "awaiting_user_confirmation",
    "approved",
    "aborted",
]
IssueSeverity = Literal["info", "warning", "error"]


class ClarificationQuestion(BaseModel):
    """A targeted question the orchestrator asks before planning further."""

    question_id: str
    question: str
    rationale: str
    required: bool = True


class ClarificationSet(BaseModel):
    """A small set of clarification questions."""

    questions: list[ClarificationQuestion] = Field(default_factory=list)


class TaskStep(BaseModel):
    """A single step in a proposed workflow plan."""

    step: int
    task_id: str | None = None
    name: str
    description: str
    source: SourceType
    reason: str = ""
    gap_notes: str | None = None
    input_bindings: dict[str, str] = Field(default_factory=dict)


class ProposedPlan(BaseModel):
    """Structured plan returned by the orchestrator."""

    task_list: list[TaskStep] = Field(default_factory=list)
    reasoning: str
    unresolved_questions: list[str] = Field(default_factory=list)


class PlanIssue(BaseModel):
    """A validation or reasoning issue with a draft plan."""

    code: str
    message: str
    severity: IssueSeverity = "error"
    step: int | None = None


class PlanRevision(BaseModel):
    """A summarized description of a plan revision."""

    summary: str
    updated_plan: ProposedPlan


class GapAnalysis(BaseModel):
    """Categorization of repo-backed, adapted, and missing steps."""

    existing_steps: list[TaskStep] = Field(default_factory=list)
    adapted_steps: list[TaskStep] = Field(default_factory=list)
    missing_steps: list[TaskStep] = Field(default_factory=list)
    validation_issues: list[PlanIssue] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    """A single trace event emitted while planning."""

    stage: str
    detail: str
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationTurn(BaseModel):
    """Structured result for one orchestration turn."""

    state: TurnState
    user_request: str
    clarification_set: ClarificationSet | None = None
    plan: ProposedPlan | None = None
    issues: list[PlanIssue] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    candidate_task_ids: list[str] = Field(default_factory=list)
    clarifications_used: dict[str, str] = Field(default_factory=dict)
    trace: list[TraceEvent] = Field(default_factory=list)

