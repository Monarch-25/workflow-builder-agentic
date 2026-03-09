"""Interactive planning REPL for the Phase 3 UX."""

from __future__ import annotations

from collections.abc import Callable

from phase2.orchestrator.plan_negotiator import PlanNegotiator, PlanSession
from phase2.orchestrator.models import OrchestrationTurn

from .formatter import PlanningFormatter


class PlanningREPL:
    """Run an interactive plan review loop."""

    def __init__(
        self,
        negotiator: PlanNegotiator,
        formatter: PlanningFormatter | None = None,
    ) -> None:
        self.negotiator = negotiator
        self.formatter = formatter or PlanningFormatter()

    def run(
        self,
        request: str,
        *,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> OrchestrationTurn:
        """Run the interactive planning flow until approval or abort."""
        session = self.negotiator.start_session(request)

        while True:
            output_fn(self.formatter.format_turn(session.current_turn))
            if session.current_turn.state in {"approved", "aborted"}:
                return session.current_turn

            if session.current_turn.state == "needs_clarification":
                answers: dict[str, str] = {}
                for question in session.current_turn.clarification_set.questions:
                    answer = input_fn(f"{question.question}\n> ").strip()
                    answers[question.question_id] = answer
                response = self.negotiator.update_clarifications(session, answers)
                output_fn(self.formatter.format_message(response.message))
                continue

            feedback = input_fn("> ").strip()
            response = self.negotiator.handle_feedback(session, feedback)
            output_fn(self.formatter.format_message(response.message))

            if response.turn.state in {"approved", "aborted"}:
                output_fn(self.formatter.format_turn(response.turn))
                return response.turn
