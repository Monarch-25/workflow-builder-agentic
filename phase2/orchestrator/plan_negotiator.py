"""Natural-language plan negotiation for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from phase1.repo.schema import AtomicTask

from phase2.core import CONFIRM_REQUIRED, IntentInferenceNode, IntentType

from .intent_parser import IntentParser
from .models import OrchestrationTurn, PlanIssue, ProposedPlan, TaskStep
from .validators import types_compatible


@dataclass(slots=True)
class PendingConfirmation:
    """Intent waiting for an explicit user confirmation."""

    intent_type: IntentType
    payload: dict[str, Any]
    original_message: str
    summary: str


@dataclass(slots=True)
class PlanSession:
    """In-memory plan review session."""

    user_request: str
    current_turn: OrchestrationTurn
    history: list[dict[str, str]] = field(default_factory=list)
    clarification_answers: dict[str, str] = field(default_factory=dict)
    pending_confirmation: PendingConfirmation | None = None


@dataclass(slots=True)
class NegotiationResponse:
    """Result returned after handling one user interaction."""

    session: PlanSession
    turn: OrchestrationTurn
    message: str


class PlanNegotiator:
    """Stateful natural-language plan negotiation."""

    def __init__(
        self,
        parser: IntentParser,
        intent_node: IntentInferenceNode | None = None,
    ) -> None:
        self.parser = parser
        self.intent_node = intent_node or IntentInferenceNode(
            parser.llm,
            backend=parser.cfg.ORCHESTRATOR_INTENT_BACKEND,
        )

    def start(self, user_query: str) -> OrchestrationTurn:
        """Start a planning turn."""
        return self.parser.parse(user_query)

    def start_session(self, user_query: str) -> PlanSession:
        """Create a new plan review session."""
        turn = self.start(user_query)
        return PlanSession(user_request=user_query, current_turn=turn)

    def answer_clarifications(
        self,
        user_query: str,
        answers: dict[str, str],
    ) -> OrchestrationTurn:
        """Resume planning after the user answers clarification questions."""
        return self.parser.parse(user_query, clarification_answers=answers)

    def update_clarifications(
        self,
        session: PlanSession,
        answers: dict[str, str],
    ) -> NegotiationResponse:
        """Apply clarification answers and refresh the current plan turn."""
        session.clarification_answers.update(answers)
        session.current_turn = self.answer_clarifications(
            session.user_request,
            session.clarification_answers,
        )
        session.pending_confirmation = None
        return NegotiationResponse(
            session=session,
            turn=session.current_turn,
            message="Updated the draft plan using your clarification answers.",
        )

    def apply_feedback(
        self,
        current_turn: OrchestrationTurn,
        feedback: str,
    ) -> OrchestrationTurn:
        """Compatibility wrapper for older callers."""
        session = PlanSession(
            user_request=current_turn.user_request,
            current_turn=current_turn,
        )
        response = self.handle_feedback(session, feedback)
        return response.turn

    def handle_feedback(
        self,
        session: PlanSession,
        feedback: str,
    ) -> NegotiationResponse:
        """Handle one natural-language message during plan review."""
        session.history.append({"role": "user", "content": feedback})

        if session.pending_confirmation is not None:
            return self._handle_confirmation_reply(session, feedback)

        plan = session.current_turn.plan or ProposedPlan(
            task_list=[],
            reasoning="No plan available yet.",
        )
        intent = self.intent_node.infer(
            user_message=feedback,
            phase="plan_review",
            current_state={"plan": [step.model_dump() for step in plan.task_list]},
            conversation_history=session.history,
        )

        if intent.confidence < 0.85 or intent.intent_type in CONFIRM_REQUIRED:
            session.pending_confirmation = PendingConfirmation(
                intent_type=intent.intent_type,
                payload=intent.payload,
                original_message=feedback,
                summary=intent.user_message_rephrased,
            )
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message=(
                    f"Understood: {intent.user_message_rephrased} "
                    "Reply `yes` to confirm or describe a different change."
                ),
            )

        return self._apply_intent(session, intent.intent_type, intent.payload, feedback)

    def _handle_confirmation_reply(
        self,
        session: PlanSession,
        feedback: str,
    ) -> NegotiationResponse:
        lowered = feedback.strip().lower()
        pending = session.pending_confirmation
        if pending is None:
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message="No pending confirmation was found.",
            )
        if lowered in {"yes", "y", "confirm", "confirmed", "do it"}:
            session.pending_confirmation = None
            return self._apply_intent(
                session,
                pending.intent_type,
                pending.payload,
                pending.original_message,
            )
        if lowered in {"no", "n", "cancel", "never mind"}:
            session.pending_confirmation = None
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message="No change applied. Describe a different change when ready.",
            )
        session.pending_confirmation = None
        return self.handle_feedback(session, feedback)

    def _apply_intent(
        self,
        session: PlanSession,
        intent_type: IntentType,
        payload: dict[str, Any],
        raw_message: str,
    ) -> NegotiationResponse:
        plan = session.current_turn.plan or ProposedPlan(
            task_list=[],
            reasoning="No plan available yet.",
        )

        if intent_type == IntentType.APPROVE:
            session.current_turn = session.current_turn.model_copy(
                update={"state": "approved"}
            )
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message="Plan approved.",
            )

        if intent_type == IntentType.REJECT_PLAN:
            session.current_turn = session.current_turn.model_copy(
                update={"state": "aborted"}
            )
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message="Plan rejected. Start a new request to generate another draft.",
            )

        if intent_type == IntentType.ABORT:
            session.current_turn = session.current_turn.model_copy(
                update={"state": "aborted"}
            )
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message="Session aborted.",
            )

        if intent_type in {IntentType.QUESTION, IntentType.CLARIFY}:
            answer = self._answer_question(raw_message, plan, payload)
            session.history.append({"role": "assistant", "content": answer})
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message=answer,
            )

        if intent_type == IntentType.MODIFY_PLAN:
            updated_plan = self._apply_plan_edit(plan, payload)
            issues = self.parser.validate_proposed_plan(updated_plan)
            state = "awaiting_user_confirmation" if not issues else "validation_failed"
            session.current_turn = session.current_turn.model_copy(
                update={
                    "plan": updated_plan,
                    "issues": issues,
                    "state": state,
                }
            )
            message = "Updated the plan." if not issues else self._format_issue_summary(issues)
            session.history.append({"role": "assistant", "content": message})
            return NegotiationResponse(
                session=session,
                turn=session.current_turn,
                message=message,
            )

        return NegotiationResponse(
            session=session,
            turn=session.current_turn,
            message="That intent is not supported in the current planning phase.",
        )

    def _apply_plan_edit(
        self,
        plan: ProposedPlan,
        payload: dict[str, Any],
    ) -> ProposedPlan:
        steps = [step.model_copy(deep=True) for step in plan.task_list]
        edits = payload.get("edits", [])
        for edit in edits:
            action = edit.get("action")
            if action == "swap":
                self._swap_steps(steps, edit["step_a"], edit["step_b"])
            elif action == "reorder":
                self._move_step(
                    steps,
                    edit["from_step"],
                    before_step=edit.get("to_before_step"),
                    after_step=edit.get("to_after_step"),
                )
            elif action == "remove":
                self._remove_step(steps, edit["step"])
            elif action == "add":
                new_step = self._build_step_from_description(edit["description"])
                self._insert_step(
                    steps,
                    new_step,
                    before_step=edit.get("before_step"),
                    after_step=edit.get("after_step"),
                    at_end=edit.get("position") == "end",
                )
        self._renumber_steps(steps)
        self._rewire_bindings(steps)
        return ProposedPlan(
            task_list=steps,
            reasoning=plan.reasoning,
            unresolved_questions=plan.unresolved_questions,
        )

    def _answer_question(
        self,
        user_message: str,
        plan: ProposedPlan,
        payload: dict[str, Any],
    ) -> str:
        if not plan.task_list:
            return "There is no draft plan yet."
        step_number = payload.get("step")
        if isinstance(step_number, int):
            step = self._find_step(plan.task_list, step_number)
            if step is not None:
                return (
                    f"Step {step.step} is `{step.name}`. "
                    f"{step.description} Reason: {step.reason or 'No additional reason captured.'}"
                )
        lowered = user_message.lower()
        if "why" in lowered or "reason" in lowered:
            return f"Plan reasoning: {plan.reasoning}"
        return "You can ask about a specific step, for example: `what does step 3 do?`"

    def _build_step_from_description(self, description: str) -> TaskStep:
        candidates = self.parser.repo.search_similar_tasks(description, top_k=3)
        if candidates:
            candidate = candidates[0]
            return TaskStep(
                step=0,
                task_id=candidate.task_id,
                name=candidate.name,
                description=candidate.description,
                source="repo",
                reason=f"Added from user feedback: {description}.",
                input_bindings=self._default_bindings(candidate),
            )
        return TaskStep(
            step=0,
            task_id=None,
            name=description.strip().title(),
            description=description.strip(),
            source="new",
            reason=f"Added from user feedback: {description}.",
            gap_notes="No repo task matched the requested addition closely enough.",
        )

    def _default_bindings(self, task: AtomicTask) -> dict[str, str]:
        bindings: dict[str, str] = {}
        for name in task.input_schema:
            if name == "timeout_sec":
                bindings[name] = "$const:10"
            elif name == "label":
                bindings[name] = "$const:Workflow Result"
            else:
                bindings[name] = f"$user:{name}"
        return bindings

    def _rewire_bindings(self, steps: list[TaskStep]) -> None:
        available_fields = self.parser.default_user_inputs()
        for step in steps:
            if not step.task_id:
                continue
            task = self.parser.repo.get_task(step.task_id)
            for input_name, input_type in task.input_schema.items():
                binding = step.input_bindings.get(input_name)
                if binding and (
                    binding.startswith("$user:") or binding.startswith("$const:")
                ):
                    continue
                if binding in available_fields and types_compatible(
                    available_fields[binding], input_type
                ):
                    continue
                replacement = self._choose_binding(input_name, input_type, available_fields)
                if replacement is not None:
                    step.input_bindings[input_name] = replacement
                elif input_name not in step.input_bindings:
                    step.input_bindings[input_name] = f"$user:{input_name}"
            available_fields.update(task.output_schema)

    @staticmethod
    def _choose_binding(
        input_name: str,
        input_type: str,
        available_fields: dict[str, str],
    ) -> str | None:
        if input_name == "timeout_sec":
            return "$const:10"
        if input_name == "label":
            return "$const:Workflow Result"
        if input_name in available_fields and types_compatible(
            available_fields[input_name],
            input_type,
        ):
            return input_name

        if input_name == "items":
            for candidate in ("urls", "live_urls", "failed_urls", "unique_items"):
                if candidate in available_fields and types_compatible(
                    available_fields[candidate],
                    input_type,
                ):
                    return candidate

        if input_name == "urls" and "unique_items" in available_fields:
            if types_compatible(available_fields["unique_items"], input_type):
                return "unique_items"

        if input_name == "result":
            for candidate in (
                "live_urls",
                "failed_urls",
                "unique_items",
                "urls",
                "raw_text",
                "records",
                "data",
            ):
                if candidate in available_fields:
                    return candidate

        for field_name, field_type in available_fields.items():
            if types_compatible(field_type, input_type):
                return field_name
        return None

    @staticmethod
    def _swap_steps(steps: list[TaskStep], step_a: int, step_b: int) -> None:
        idx_a = PlanNegotiator._find_index(steps, step_a)
        idx_b = PlanNegotiator._find_index(steps, step_b)
        if idx_a is None or idx_b is None:
            return
        steps[idx_a], steps[idx_b] = steps[idx_b], steps[idx_a]

    @staticmethod
    def _move_step(
        steps: list[TaskStep],
        from_step: int,
        *,
        before_step: int | None = None,
        after_step: int | None = None,
    ) -> None:
        idx = PlanNegotiator._find_index(steps, from_step)
        if idx is None:
            return
        step = steps.pop(idx)
        target_step = before_step if before_step is not None else after_step
        target_idx = PlanNegotiator._find_index(steps, target_step) if target_step is not None else None
        if target_idx is None:
            steps.append(step)
            return
        insert_idx = target_idx if before_step is not None else target_idx + 1
        steps.insert(insert_idx, step)

    @staticmethod
    def _remove_step(steps: list[TaskStep], step_number: int) -> None:
        idx = PlanNegotiator._find_index(steps, step_number)
        if idx is not None:
            steps.pop(idx)

    @staticmethod
    def _insert_step(
        steps: list[TaskStep],
        new_step: TaskStep,
        *,
        before_step: int | None = None,
        after_step: int | None = None,
        at_end: bool = False,
    ) -> None:
        if at_end or (before_step is None and after_step is None):
            steps.append(new_step)
            return
        target_step = before_step if before_step is not None else after_step
        idx = PlanNegotiator._find_index(steps, target_step)
        if idx is None:
            steps.append(new_step)
            return
        insert_idx = idx if before_step is not None else idx + 1
        steps.insert(insert_idx, new_step)

    @staticmethod
    def _renumber_steps(steps: list[TaskStep]) -> None:
        for index, step in enumerate(steps, start=1):
            step.step = index

    @staticmethod
    def _find_index(steps: list[TaskStep], step_number: int | None) -> int | None:
        if step_number is None:
            return None
        for index, step in enumerate(steps):
            if step.step == step_number:
                return index
        return None

    @staticmethod
    def _find_step(steps: list[TaskStep], step_number: int) -> TaskStep | None:
        for step in steps:
            if step.step == step_number:
                return step
        return None

    @staticmethod
    def _format_issue_summary(issues: list[PlanIssue]) -> str:
        details = "; ".join(issue.message for issue in issues[:3])
        return f"Updated the plan, but validation found issues: {details}"
