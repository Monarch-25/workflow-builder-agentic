Story Name: Implement the Intent Inference Node and Natural Language Plan Negotiation Loop
What:

Build the IntentInferenceNode — a dedicated Claude Sonnet call at every human-in-the-loop boundary that converts free-form user text into a structured InferredIntent (type, confidence, payload, rephrased understanding), covering all intent types across plan review, task build, and workflow verification phases
Complete the PlanNegotiator to use IntentInferenceNode at every turn so users can edit plans in natural language ("swap 2 and 3", "add a dedup step after URL extraction", "remove the failure analysis") instead of rigid command syntax
Implement _apply_plan_edit() — a Claude-powered plan mutation function that takes the current plan and a structured edit payload and returns the correctly updated plan JSON, maintaining step numbering and schema chain integrity
Add the confidence-gated echo-back: for intents below 0.85 confidence or for destructive intents (MODIFY_PLAN, REJECT_PLAN, ABORT), the system prints its understanding before acting, giving the user a chance to correct misinterpretation

Why:

The Intent Inference Node is what makes the Workflow Automation Engine MVP feel like a natural conversation rather than a command-line tool — it is a core product differentiator for a technical banking audience who will express intent in varied, abbreviated, and context-dependent language
Removing rigid command parsing eliminates an entire class of user errors (mistyped commands, wrong step numbers, unexpected phrasing) that would otherwise require error handling and user re-education
The confidence gate and echo-back are important safeguards in a banking context where an accidental REJECT_PLAN or ABORT on a complex workflow would force the user to restart from scratch — this mitigates that risk without adding friction to confident, clear intents
The PlanNegotiator's multi-turn history threading ensures the LLM has full context of prior edits when applying a new one, preventing contradictory or regressive plan mutations

Acceptance Criteria:

Given the message "yeah looks good but move the URL check before dedup and drop the last step", IntentInferenceNode.infer() returns intent_type: MODIFY_PLAN with a payload containing two structured edits (a reorder and a remove), without the user typing any command syntax
For an ambiguous message like "maybe change it?", the system prints a rephrased understanding string before making any plan mutation, and the plan is only changed after the user's next confirming message
The full plan negotiation loop handles at minimum 5 consecutive edits in a single session without losing prior context or corrupting step numbering, verifiable by a reviewer stepping through the REPL manually
IntentInferenceNode.infer() correctly routes to QUESTION (not APPROVE) when the user asks "what does the dedup step actually do?", and the session does not advance state

Artifacts:

core/intent_infer.py — IntentType enum, InferredIntent schema, IntentInferenceNode class, all prompts
orchestrator/plan_negotiator.py — completed with _apply_plan_edit() and intent routing
PHASE_VALID_INTENTS mapping and CONFIRM_REQUIRED set
Integration test: full plan negotiation session with 4 sequential NL edits ending in approval