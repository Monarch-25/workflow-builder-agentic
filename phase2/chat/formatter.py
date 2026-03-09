"""Human-readable formatting helpers for the planning REPL."""

from __future__ import annotations

from phase2.orchestrator.models import OrchestrationTurn, ProposedPlan, TaskStep


class PlanningFormatter:
    """Render planning turns in a conversational, review-friendly format."""

    def format_turn(self, turn: OrchestrationTurn) -> str:
        sections = []
        if turn.clarification_set and turn.clarification_set.questions:
            sections.append(self.format_clarifications(turn))
        if turn.plan is not None:
            sections.append(self.format_plan(turn.plan))
        if turn.issues:
            sections.append(self.format_issues(turn))
        sections.append(self.format_prompt(turn))
        return "\n\n".join(section for section in sections if section.strip())

    def format_clarifications(self, turn: OrchestrationTurn) -> str:
        lines = ["I need a couple of details before I can tighten the plan:"]
        for question in turn.clarification_set.questions:
            lines.append(f"- {question.question} ({question.rationale})")
        return "\n".join(lines)

    def format_plan(self, plan: ProposedPlan) -> str:
        lines = [f"Draft plan: {plan.reasoning}"]
        for step in plan.task_list:
            lines.append(self.format_step(step))
        if plan.unresolved_questions:
            lines.append("Unresolved:")
            for item in plan.unresolved_questions:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def format_step(self, step: TaskStep) -> str:
        suffix = f" [{step.source}]"
        if step.gap_notes:
            suffix += f" - {step.gap_notes}"
        return f"{step.step}. {step.name}{suffix}"

    def format_issues(self, turn: OrchestrationTurn) -> str:
        lines = ["Validation issues:"]
        for issue in turn.issues:
            prefix = f"step {issue.step}" if issue.step else "plan"
            lines.append(f"- {prefix}: {issue.message}")
        return "\n".join(lines)

    def format_message(self, message: str) -> str:
        return message

    def format_prompt(self, turn: OrchestrationTurn) -> str:
        if turn.state == "needs_clarification":
            return "Answer the questions above in your own words."
        if turn.state == "approved":
            return "Plan approved."
        if turn.state == "aborted":
            return "Session ended."
        return (
            "Reply in natural language. You can approve, ask a question, "
            "or request an edit like 'move step 3 before step 2'."
        )

