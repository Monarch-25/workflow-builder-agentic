"""Clarification-first intent parsing and draft plan generation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol

from phase1.repo.schema import AtomicTask

from phase2.core.config import Config

from .models import (
    ClarificationQuestion,
    ClarificationSet,
    OrchestrationTurn,
    PlanIssue,
    ProposedPlan,
    TaskStep,
)
from .tool_specs import build_orchestrator_tools
from .tracing import TraceRecorder
from .validators import TaskRepoProtocol, validate_plan

ORCHESTRATOR_SYSTEM = """
You are an interactive workflow orchestration assistant operating on Bedrock.
Ask targeted clarification questions when critical requirements are missing.
Prefer existing repo tasks. Use new tasks only after retrieval is exhausted.
Make every data handoff explicit with input bindings.
""".strip()


class SearchableTaskRepo(TaskRepoProtocol, Protocol):
    """Minimal repo surface needed by the parser."""

    def list_all_tasks(self) -> list[str]:
        ...

    def search_similar_tasks(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[AtomicTask]:
        ...


class PlanningBrain(Protocol):
    """Optional planning brain used to ask questions and draft plans."""

    def propose_clarifications(
        self,
        user_query: str,
        clarification_answers: Mapping[str, str],
    ) -> ClarificationSet | None:
        ...

    def draft_plan(
        self,
        user_query: str,
        candidate_tasks: list[AtomicTask],
        clarification_answers: Mapping[str, str],
    ) -> ProposedPlan:
        ...

    def revise_plan(
        self,
        user_query: str,
        current_plan: ProposedPlan,
        issues: list[PlanIssue],
        candidate_tasks: list[AtomicTask],
        clarification_answers: Mapping[str, str],
    ) -> ProposedPlan | ClarificationSet | None:
        ...


class HeuristicPlanningBrain:
    """Local deterministic fallback used until live Bedrock orchestration is wired."""

    def propose_clarifications(
        self,
        user_query: str,
        clarification_answers: Mapping[str, str],
    ) -> ClarificationSet | None:
        lowered = user_query.lower()
        questions: list[ClarificationQuestion] = []
        artifact_terms = {
            "pdf",
            "csv",
            "excel",
            "url",
            "urls",
            "swift",
            "html",
            "image",
            "invoice",
            "transaction",
        }

        if (
            len(lowered.split()) < 4
            or ("process" in lowered and not any(term in lowered for term in artifact_terms))
        ):
            if "input_artifact" not in clarification_answers:
                questions.append(
                    ClarificationQuestion(
                        question_id="input_artifact",
                        question="What kind of input are we processing?",
                        rationale=(
                            "The request is too broad to retrieve the right repo tasks."
                        ),
                    )
                )
            if "desired_output" not in clarification_answers:
                questions.append(
                    ClarificationQuestion(
                        question_id="desired_output",
                        question="What output do you want the workflow to return?",
                        rationale=(
                            "The planner needs the expected result to choose the last step."
                        ),
                    )
                )

        if "swift" in lowered and not re.search(r"mt\d{3}", lowered):
            if "swift_message_type" not in clarification_answers:
                questions.append(
                    ClarificationQuestion(
                        question_id="swift_message_type",
                        question="Which SWIFT message type should the parser target?",
                        rationale=(
                            "The current repo only has partial SWIFT coverage by format."
                        ),
                    )
                )

        if questions:
            return ClarificationSet(questions=questions[:3])
        return None

    def draft_plan(
        self,
        user_query: str,
        candidate_tasks: list[AtomicTask],
        clarification_answers: Mapping[str, str],
    ) -> ProposedPlan:
        lowered = user_query.lower()
        task_map = {task.task_id: task for task in candidate_tasks}

        if self._has_all(
            task_map,
            "upload_file_v1",
            "extract_text_from_pdf_v1",
            "extract_urls_from_text_v1",
            "check_url_liveness_v1",
        ) and "pdf" in lowered and "url" in lowered and any(
            term in lowered for term in ("working", "live", "liveness")
        ):
            return ProposedPlan(
                reasoning=(
                    "The request maps cleanly to upload, PDF text extraction, "
                    "URL extraction, and URL liveness checks using existing repo tasks."
                ),
                task_list=[
                    TaskStep(
                        step=1,
                        task_id="upload_file_v1",
                        name="Upload File",
                        description=task_map["upload_file_v1"].description,
                        source="repo",
                        reason="Normalize the user-supplied file path into the workflow workspace.",
                        input_bindings={"file_path": "$user:file_path"},
                    ),
                    TaskStep(
                        step=2,
                        task_id="extract_text_from_pdf_v1",
                        name="Extract Text from PDF",
                        description=task_map["extract_text_from_pdf_v1"].description,
                        source="repo",
                        reason="Convert the PDF into raw text for downstream extraction.",
                        input_bindings={"file_path": "normalized_path"},
                    ),
                    TaskStep(
                        step=3,
                        task_id="extract_urls_from_text_v1",
                        name="Extract URLs from Text",
                        description=task_map["extract_urls_from_text_v1"].description,
                        source="repo",
                        reason="Extract candidate URLs from the PDF text.",
                        input_bindings={"raw_text": "raw_text"},
                    ),
                    TaskStep(
                        step=4,
                        task_id="check_url_liveness_v1",
                        name="Check URL Liveness",
                        description=task_map["check_url_liveness_v1"].description,
                        source="repo",
                        reason="Verify which extracted URLs are still reachable.",
                        input_bindings={
                            "urls": "urls",
                            "timeout_sec": "$const:10",
                        },
                    ),
                ],
            )

        if "swift" in lowered and "mt950" in lowered:
            return ProposedPlan(
                reasoning=(
                    "The repo contains SWIFT parsing support, but not specific support "
                    "for MT950 reconciliation reports."
                ),
                task_list=[
                    TaskStep(
                        step=1,
                        task_id=None,
                        name="Parse SWIFT MT950 Reconciliation Report",
                        description=(
                            "Parse an MT950 reconciliation report into a structured ledger view."
                        ),
                        source="new",
                        reason="The repo does not contain an MT950 reconciliation parser.",
                        gap_notes=(
                            "Existing SWIFT support is limited to other message types."
                        ),
                    )
                ],
            )

        for candidate in candidate_tasks:
            if not candidate.input_schema:
                continue
            input_bindings = {
                field_name: f"$user:{field_name}"
                for field_name in candidate.input_schema
            }
            return ProposedPlan(
                reasoning=(
                    "A single repo task appears to cover the request closely enough "
                    "for an initial draft plan."
                ),
                task_list=[
                    TaskStep(
                        step=1,
                        task_id=candidate.task_id,
                        name=candidate.name,
                        description=candidate.description,
                        source="repo",
                        reason="Best available repo match from retrieval.",
                        input_bindings=input_bindings,
                    )
                ],
            )

        return ProposedPlan(
            reasoning=(
                "No strong repo candidate was found, so the work is marked as a new step."
            ),
            task_list=[
                TaskStep(
                    step=1,
                    task_id=None,
                    name="Create New Atomic Task",
                    description=user_query,
                    source="new",
                    reason="No task in the repo matched with enough confidence.",
                    gap_notes="Task Builder will need to create this capability.",
                )
            ],
        )

    def revise_plan(
        self,
        user_query: str,
        current_plan: ProposedPlan,
        issues: list[PlanIssue],
        candidate_tasks: list[AtomicTask],
        clarification_answers: Mapping[str, str],
    ) -> ProposedPlan | ClarificationSet | None:
        if any(issue.code == "missing_input" for issue in issues):
            questions = []
            if "desired_output" not in clarification_answers:
                questions.append(
                    ClarificationQuestion(
                        question_id="desired_output",
                        question="What should the workflow return after processing?",
                        rationale=(
                            "The current draft cannot connect all inputs without a clearer end goal."
                        ),
                    )
                )
            if questions:
                return ClarificationSet(questions=questions)
        return current_plan

    @staticmethod
    def _has_all(task_map: dict[str, AtomicTask], *task_ids: str) -> bool:
        return all(task_id in task_map for task_id in task_ids)


class IntentParser:
    """Build a draft plan using clarification, retrieval, and validation."""

    def __init__(
        self,
        repo: SearchableTaskRepo,
        cfg: Config | None = None,
        llm: object | None = None,
        brain: PlanningBrain | None = None,
    ) -> None:
        self.repo = repo
        self.cfg = cfg or Config()
        self.llm = llm
        self.brain = brain or HeuristicPlanningBrain()
        self.system_prompt = ORCHESTRATOR_SYSTEM

    def load_all_tasks(self) -> list[AtomicTask]:
        """Load all registered repo tasks in stable order."""
        return [self.repo.get_task(task_id) for task_id in sorted(self.repo.list_all_tasks())]

    def build_tools(self) -> list[dict]:
        """Build the Bedrock tool list used by the orchestrator."""
        return build_orchestrator_tools(
            self.load_all_tasks(),
            anchor_task_ids=self.cfg.anchor_task_ids,
        )

    def prepare_llm_request(self, user_query: str) -> dict[str, object] | None:
        """Prepare the default orchestration request without executing it."""
        if self.llm is None:
            return None
        if not hasattr(self.llm, "build_orchestrator_request"):
            return None
        return self.llm.build_orchestrator_request(
            user_text=user_query,
            system=self.system_prompt,
            tools=self.build_tools(),
            prompt_cache=self.cfg.ORCHESTRATOR_ENABLE_PROMPT_CACHING,
        )

    def derive_search_queries(
        self,
        user_query: str,
        clarification_answers: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Generate short, targeted retrieval queries."""
        lowered = user_query.lower()
        queries = [lowered]
        if "pdf" in lowered:
            queries.append("pdf text extraction")
        if "url" in lowered or "urls" in lowered:
            queries.append("url extraction")
        if any(term in lowered for term in ("working", "live", "liveness")):
            queries.append("url liveness check")
        if "swift" in lowered:
            queries.append("swift parsing")
        if clarification_answers:
            for value in clarification_answers.values():
                normalized = value.strip().lower()
                if normalized:
                    queries.append(normalized)

        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            if query in seen:
                continue
            seen.add(query)
            deduped.append(query)
            if len(deduped) >= self.cfg.ORCHESTRATOR_MAX_SEARCH_ROUNDS:
                break
        return deduped

    def retrieve_candidate_tasks(
        self,
        user_query: str,
        clarification_answers: Mapping[str, str] | None = None,
        trace: TraceRecorder | None = None,
    ) -> tuple[list[str], list[AtomicTask]]:
        """Run one or more local retrieval passes and merge candidate tasks."""
        queries = self.derive_search_queries(user_query, clarification_answers)
        by_task_id: dict[str, AtomicTask] = {}

        for query in queries:
            matches = self.repo.search_similar_tasks(
                query,
                top_k=self.cfg.ORCHESTRATOR_CANDIDATE_TOP_K,
            )
            if trace is not None:
                trace.add(
                    "search",
                    "Executed semantic task search.",
                    query=query,
                    returned=[task.task_id for task in matches],
                )
            for task in matches:
                by_task_id.setdefault(task.task_id, task)
            if len(by_task_id) >= self.cfg.ORCHESTRATOR_MIN_CANDIDATES:
                break

        return queries, list(by_task_id.values())

    def parse(
        self,
        user_query: str,
        clarification_answers: Mapping[str, str] | None = None,
    ) -> OrchestrationTurn:
        """Return the next orchestration turn for the user request."""
        clarifications = dict(clarification_answers or {})
        trace = TraceRecorder(enabled=self.cfg.ORCHESTRATOR_TRACE_ENABLED)
        trace.add("start", "Started orchestration turn.", user_query=user_query)

        clarification_set = self.brain.propose_clarifications(user_query, clarifications)
        if clarification_set is not None:
            unanswered = [
                question
                for question in clarification_set.questions
                if question.question_id not in clarifications
            ]
            if unanswered:
                trace.add(
                    "clarify",
                    "Returning clarification questions before plan generation.",
                    question_ids=[question.question_id for question in unanswered],
                )
                return OrchestrationTurn(
                    state="needs_clarification",
                    user_request=user_query,
                    clarification_set=ClarificationSet(questions=unanswered),
                    clarifications_used=clarifications,
                    trace=trace.events,
                )

        search_queries, candidate_tasks = self.retrieve_candidate_tasks(
            user_query,
            clarifications,
            trace=trace,
        )
        trace.add(
            "retrieval_complete",
            "Collected candidate tasks for planning.",
            candidate_task_ids=[task.task_id for task in candidate_tasks],
        )

        plan = self.brain.draft_plan(user_query, candidate_tasks, clarifications)
        trace.add(
            "draft_plan",
            "Generated draft plan.",
            task_ids=[step.task_id for step in plan.task_list],
        )

        issues = validate_plan(
            plan,
            self.repo,
            user_inputs={
                "file_path": "str",
                "raw_text": "str",
                "text": "str",
                "urls": "list[str]",
                "records": "list[dict]",
                "data": "dict",
            },
        )

        if issues:
            trace.add(
                "validation_failed",
                "Draft plan failed validation.",
                issues=[issue.code for issue in issues],
            )
            revised = self.brain.revise_plan(
                user_query,
                plan,
                issues,
                candidate_tasks,
                clarifications,
            )
            if isinstance(revised, ClarificationSet):
                return OrchestrationTurn(
                    state="needs_clarification",
                    user_request=user_query,
                    clarification_set=revised,
                    plan=plan,
                    issues=issues,
                    search_queries=search_queries,
                    candidate_task_ids=[task.task_id for task in candidate_tasks],
                    clarifications_used=clarifications,
                    trace=trace.events,
                )
            if isinstance(revised, ProposedPlan):
                plan = revised
                issues = validate_plan(
                    plan,
                    self.repo,
                    user_inputs={
                        "file_path": "str",
                        "raw_text": "str",
                        "text": "str",
                        "urls": "list[str]",
                        "records": "list[dict]",
                        "data": "dict",
                    },
                )

        state = "awaiting_user_confirmation" if not issues else "validation_failed"
        return OrchestrationTurn(
            state=state,
            user_request=user_query,
            plan=plan,
            issues=issues,
            search_queries=search_queries,
            candidate_task_ids=[task.task_id for task in candidate_tasks],
            clarifications_used=clarifications,
            trace=trace.events,
        )

