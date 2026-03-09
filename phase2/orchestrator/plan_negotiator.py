"""Minimal interactive review loop for orchestrator plans."""

from __future__ import annotations

from collections.abc import Mapping

from .intent_parser import IntentParser
from .models import OrchestrationTurn

APPROVE_WORDS = {"approve", "approved", "yes", "looks good", "ship it"}
REJECT_WORDS = {"reject", "cancel", "stop", "abort", "no"}


class PlanNegotiator:
    """Small helper around ``IntentParser`` for review-time iteration."""

    def __init__(self, parser: IntentParser) -> None:
        self.parser = parser

    def start(self, user_query: str) -> OrchestrationTurn:
        """Start a planning turn."""
        return self.parser.parse(user_query)

    def answer_clarifications(
        self,
        user_query: str,
        answers: Mapping[str, str],
    ) -> OrchestrationTurn:
        """Resume planning after the user answers clarification questions."""
        return self.parser.parse(user_query, clarification_answers=answers)

    def apply_feedback(
        self,
        current_turn: OrchestrationTurn,
        feedback: str,
    ) -> OrchestrationTurn:
        """Apply a simple approval, rejection, or revision request."""
        lowered = feedback.strip().lower()
        if lowered in APPROVE_WORDS:
            return current_turn.model_copy(update={"state": "approved"})
        if lowered in REJECT_WORDS:
            return current_turn.model_copy(update={"state": "aborted"})
        revised_request = f"{current_turn.user_request}\nRevision request: {feedback}"
        return self.parser.parse(
            revised_request,
            clarification_answers=current_turn.clarifications_used,
        )

