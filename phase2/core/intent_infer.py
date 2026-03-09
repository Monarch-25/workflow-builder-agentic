"""Natural-language intent inference for human-in-the-loop planning."""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a workflow-building system used by banking analysts.
Classify the user's message relative to the current workflow phase.
Return JSON only, matching the requested schema exactly.
""".strip()

INTENT_INFERENCE_PROMPT = """
CURRENT PHASE: {phase}

CURRENT STATE:
{current_state}

VALID INTENTS:
{valid_intents}

USER MESSAGE:
{user_message}

Classify the user's intent. If they are modifying the plan, extract structured edits.
Keep the payload minimal but precise.
""".strip()


class IntentType(str, Enum):
    """User intents supported across workflow phases."""

    APPROVE = "approve"
    MODIFY_PLAN = "modify_plan"
    REJECT_PLAN = "reject_plan"

    APPROVE_TASK = "approve_task"
    MODIFY_TASK = "modify_task"
    RETEST_TASK = "retest_task"
    SKIP_TASK = "skip_task"

    APPROVE_WORKFLOW = "approve_workflow"
    MODIFY_WORKFLOW = "modify_workflow"
    RERUN_WORKFLOW = "rerun_workflow"

    QUESTION = "question"
    CLARIFY = "clarify"
    ABORT = "abort"


class InferredIntent(BaseModel):
    """Structured intent returned by the inference node."""

    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    user_message_rephrased: str


PHASE_VALID_INTENTS: dict[str, tuple[IntentType, ...]] = {
    "plan_review": (
        IntentType.APPROVE,
        IntentType.MODIFY_PLAN,
        IntentType.REJECT_PLAN,
        IntentType.QUESTION,
        IntentType.CLARIFY,
        IntentType.ABORT,
    ),
    "task_build": (
        IntentType.APPROVE_TASK,
        IntentType.MODIFY_TASK,
        IntentType.RETEST_TASK,
        IntentType.SKIP_TASK,
        IntentType.QUESTION,
        IntentType.ABORT,
    ),
    "workflow_verify": (
        IntentType.APPROVE_WORKFLOW,
        IntentType.MODIFY_WORKFLOW,
        IntentType.RERUN_WORKFLOW,
        IntentType.QUESTION,
        IntentType.ABORT,
    ),
}

CONFIRM_REQUIRED = {
    IntentType.MODIFY_PLAN,
    IntentType.REJECT_PLAN,
    IntentType.MODIFY_WORKFLOW,
    IntentType.ABORT,
}

APPROVE_WORDS = {
    "approve",
    "approved",
    "yes",
    "y",
    "looks good",
    "lgtm",
    "ship it",
    "go ahead",
}
REJECT_WORDS = {"reject", "start over", "redo plan", "scrap this"}
ABORT_WORDS = {"abort", "cancel", "stop everything", "never mind", "exit"}
QUESTION_PREFIXES = ("what", "why", "how", "does", "can", "could", "which")
CLARIFY_WORDS = {"clarify", "explain", "summarize", "walk me through"}
MODIFY_HINTS = {
    "move",
    "swap",
    "drop",
    "remove",
    "delete",
    "add",
    "insert",
    "change",
    "edit",
    "replace",
}


class IntentInferenceNode:
    """Infer user intent from casual natural-language feedback."""

    def __init__(
        self,
        llm: Any | None = None,
        *,
        backend: str = "bedrock",
    ) -> None:
        self.llm = llm
        self.backend = backend

    def infer(
        self,
        user_message: str,
        phase: str,
        current_state: Any,
        conversation_history: list[dict],
    ) -> InferredIntent:
        """Infer intent with Bedrock by default and heuristics as fallback."""
        if self._should_use_bedrock():
            try:
                return self._infer_with_bedrock(
                    user_message=user_message,
                    phase=phase,
                    current_state=current_state,
                    conversation_history=conversation_history,
                )
            except Exception:
                # Fall back to local heuristics so planning remains available
                # when Bedrock is disabled, unavailable, or under test.
                pass
        normalized = self._normalize(user_message)
        plan_steps = (
            list(current_state.get("plan", []))
            if isinstance(current_state, dict)
            else []
        )

        if phase == "plan_review":
            return self._infer_plan_review(normalized, plan_steps)
        if normalized in ABORT_WORDS:
            return InferredIntent(
                intent_type=IntentType.ABORT,
                confidence=0.98,
                user_message_rephrased="You want to stop the current workflow session.",
            )
        return InferredIntent(
            intent_type=IntentType.CLARIFY,
            confidence=0.55,
            user_message_rephrased="You want the system to explain or restate the current state.",
        )

    def _should_use_bedrock(self) -> bool:
        return self.backend == "bedrock" and self.llm is not None

    def _infer_with_bedrock(
        self,
        *,
        user_message: str,
        phase: str,
        current_state: Any,
        conversation_history: list[dict],
    ) -> InferredIntent:
        prompt = INTENT_INFERENCE_PROMPT.format(
            phase=phase,
            current_state=json.dumps(current_state, indent=2, default=str),
            valid_intents=", ".join(
                intent.value for intent in PHASE_VALID_INTENTS.get(phase, ())
            ),
            user_message=user_message,
        )
        messages = list(conversation_history)
        messages.append(
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        )
        return self.llm.converse_structured(
            system=INTENT_SYSTEM_PROMPT,
            messages=messages,
            output_schema=InferredIntent,
            schema_name="inferred_intent",
            schema_description=(
                "Structured user intent for plan review, task building, and workflow verification."
            ),
        )

    def _infer_plan_review(
        self,
        user_message: str,
        plan_steps: list[dict[str, Any]],
    ) -> InferredIntent:
        if user_message in ABORT_WORDS:
            return InferredIntent(
                intent_type=IntentType.ABORT,
                confidence=0.99,
                user_message_rephrased="You want to abort the current planning session.",
            )

        if user_message in REJECT_WORDS:
            return InferredIntent(
                intent_type=IntentType.REJECT_PLAN,
                confidence=0.97,
                user_message_rephrased="You want to reject this plan and start again.",
            )

        edits = self._extract_plan_edits(user_message, plan_steps)
        if edits:
            return InferredIntent(
                intent_type=IntentType.MODIFY_PLAN,
                confidence=0.91,
                payload={"edits": edits},
                user_message_rephrased=self._summarize_edits(edits),
            )

        if any(hint in user_message for hint in MODIFY_HINTS):
            return InferredIntent(
                intent_type=IntentType.MODIFY_PLAN,
                confidence=0.52,
                payload={"raw_instruction": user_message},
                user_message_rephrased=(
                    "You want to change the current plan, but the requested edit is ambiguous."
                ),
            )

        if self._is_question(user_message):
            return self._build_question_intent(user_message, plan_steps)

        if any(word in user_message for word in CLARIFY_WORDS):
            return InferredIntent(
                intent_type=IntentType.CLARIFY,
                confidence=0.88,
                user_message_rephrased="You want an explanation of the current plan.",
            )

        if any(word in user_message for word in APPROVE_WORDS):
            return InferredIntent(
                intent_type=IntentType.APPROVE,
                confidence=0.96,
                user_message_rephrased="You approve the current plan.",
            )

        return InferredIntent(
            intent_type=IntentType.CLARIFY,
            confidence=0.45,
            user_message_rephrased=(
                "Your last message is unclear, so the system needs clarification before acting."
            ),
        )

    @staticmethod
    def _normalize(user_message: str) -> str:
        return re.sub(r"\s+", " ", user_message.strip().lower())

    def _is_question(self, user_message: str) -> bool:
        return user_message.endswith("?") or user_message.startswith(QUESTION_PREFIXES)

    def _build_question_intent(
        self,
        user_message: str,
        plan_steps: list[dict[str, Any]],
    ) -> InferredIntent:
        step = self._resolve_step_reference(user_message, plan_steps)
        payload: dict[str, Any] = {}
        if step is not None:
            payload["step"] = step
        return InferredIntent(
            intent_type=IntentType.QUESTION,
            confidence=0.95,
            payload=payload,
            user_message_rephrased="You are asking for more detail about the current plan.",
        )

    def _extract_plan_edits(
        self,
        user_message: str,
        plan_steps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        clauses = [
            clause.strip(" ,.")
            for clause in re.split(
                r"\bbut\b|,|\band (?=(?:move|swap|drop|remove|delete|add|insert|change|edit|replace)\b)",
                user_message,
            )
            if clause.strip(" ,.")
        ]
        edits: list[dict[str, Any]] = []
        for clause in clauses:
            swap_match = re.search(r"swap(?: step)? (\d+) (?:and|with) (\d+)", clause)
            if swap_match:
                edits.append(
                    {
                        "action": "swap",
                        "step_a": int(swap_match.group(1)),
                        "step_b": int(swap_match.group(2)),
                    }
                )
                continue

            move_match = re.search(
                r"move (?P<subject>.+?) (?P<direction>before|after) (?P<target>.+)",
                clause,
            )
            if move_match:
                from_step = self._resolve_step_reference(
                    move_match.group("subject"),
                    plan_steps,
                )
                target_step = self._resolve_step_reference(
                    move_match.group("target"),
                    plan_steps,
                )
                if from_step is not None and target_step is not None:
                    edit = {
                        "action": "reorder",
                        "from_step": from_step,
                    }
                    if move_match.group("direction") == "before":
                        edit["to_before_step"] = target_step
                    else:
                        edit["to_after_step"] = target_step
                    edits.append(edit)
                    continue

            remove_match = re.search(
                r"(?:drop|remove|delete) (?P<target>.+)",
                clause,
            )
            if remove_match:
                step = self._resolve_step_reference(
                    remove_match.group("target"),
                    plan_steps,
                )
                if step is not None:
                    edits.append({"action": "remove", "step": step})
                    continue

            add_match = re.search(
                r"add (?:a |an )?(?P<description>.+?) step (?P<direction>before|after) (?P<target>.+)",
                clause,
            )
            if add_match:
                target_step = self._resolve_step_reference(
                    add_match.group("target"),
                    plan_steps,
                )
                if target_step is not None:
                    edit = {
                        "action": "add",
                        "description": add_match.group("description").strip(),
                    }
                    if add_match.group("direction") == "before":
                        edit["before_step"] = target_step
                    else:
                        edit["after_step"] = target_step
                    edits.append(edit)
                    continue

            add_end_match = re.search(
                r"add (?:a |an )?(?P<description>.+?) step(?: at the end)?$",
                clause,
            )
            if add_end_match:
                edits.append(
                    {
                        "action": "add",
                        "description": add_end_match.group("description").strip(),
                        "position": "end",
                    }
                )
        return edits

    def _resolve_step_reference(
        self,
        raw_reference: str,
        plan_steps: list[dict[str, Any]],
    ) -> int | None:
        reference = raw_reference.strip().lower()
        if not reference:
            return None
        number_match = re.search(r"step (\d+)|^(\d+)$", reference)
        if number_match:
            return int(number_match.group(1) or number_match.group(2))
        if "last step" in reference or reference == "last":
            return max((step.get("step", 0) for step in plan_steps), default=None)

        reference = re.sub(r"^(the|a|an) ", "", reference)
        reference = re.sub(
            r"\b(what|why|how|does|do|actually|please|could|can|would|step|the)\b",
            " ",
            reference,
        )
        reference = re.sub(r"\s+", " ", reference).strip()
        candidates: list[tuple[int, int]] = []
        tokens = set(re.findall(r"[a-z0-9]+", reference))
        for step in plan_steps:
            haystack = " ".join(
                [
                    str(step.get("name", "")).lower(),
                    str(step.get("description", "")).lower(),
                ]
            )
            if reference and reference in haystack:
                candidates.append((step.get("step", 0), len(tokens) + 5))
                continue
            score = sum(1 for token in tokens if token and token in haystack)
            if score:
                candidates.append((step.get("step", 0), score))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[1], item[0]))
        return candidates[0][0]

    @staticmethod
    def _summarize_edits(edits: list[dict[str, Any]]) -> str:
        parts = []
        for edit in edits:
            action = edit["action"]
            if action == "swap":
                parts.append(
                    f"swap step {edit['step_a']} with step {edit['step_b']}"
                )
            elif action == "reorder":
                if "to_before_step" in edit:
                    parts.append(
                        f"move step {edit['from_step']} before step {edit['to_before_step']}"
                    )
                else:
                    parts.append(
                        f"move step {edit['from_step']} after step {edit['to_after_step']}"
                    )
            elif action == "remove":
                parts.append(f"remove step {edit['step']}")
            elif action == "add":
                description = edit["description"]
                if "after_step" in edit:
                    parts.append(
                        f"add '{description}' after step {edit['after_step']}"
                    )
                elif "before_step" in edit:
                    parts.append(
                        f"add '{description}' before step {edit['before_step']}"
                    )
                else:
                    parts.append(f"add '{description}' at the end")
        if not parts:
            return "You want to change the current plan."
        return "You want to " + "; ".join(parts) + "."
