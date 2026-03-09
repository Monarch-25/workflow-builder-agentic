# Phase 2 Chat Session Transition

## Purpose

This document explains the changes made to move Phase 2 from a single-shot planning output into a back-and-forth planning session that behaves more like a co-planning assistant.

## Before

The original Phase 2 implementation behaved like a one-turn planner:

- user passed a request
- the parser produced a single `OrchestrationTurn`
- the CLI printed the final JSON
- there was no persistent session state
- there was no natural-language edit loop
- there was no approval / rejection / clarification conversation

In practice, this meant the tool felt like a structured API wrapper rather than a planning assistant.

Relevant behavior:

- [startup.py](/Users/mozart/Documents/workflow_builder/phase2/startup.py) originally ran one turn and printed JSON
- [intent_parser.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/intent_parser.py) could represent states like `needs_clarification`, but there was no user-facing loop around them
- [plan_negotiator.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/plan_negotiator.py) was initially only a thin helper that reparsed feedback

## After

Phase 2 now supports an actual planning conversation:

- the system can ask clarification questions
- the user can answer and continue the same planning session
- the user can edit the plan in natural language
- the system can ask for confirmation before risky edits
- the user can ask questions about the current plan without advancing state
- the session can end in approval, rejection, or abort

This is still Phase 3 planning behavior, not workflow execution, but the UX now behaves like a real co-planning loop instead of a one-shot dump.

## What Changed

### 1. Intent inference was added

New file:

- [intent_infer.py](/Users/mozart/Documents/workflow_builder/phase2/core/intent_infer.py)

This added:

- `IntentType`
- `InferredIntent`
- phase-valid intent mappings
- confirmation-required intent handling
- natural-language parsing for:
  - approve
  - modify plan
  - reject plan
  - question
  - clarify
  - abort

Important detail:

- Bedrock Claude is now the default inference path
- local heuristics are only the fallback path

## 2. The plan negotiator became stateful

Updated file:

- [plan_negotiator.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/plan_negotiator.py)

The negotiator now keeps:

- the current plan turn
- session history
- clarification answers
- pending confirmation state

It now supports:

- multi-turn edits
- confirmation gating for destructive or ambiguous actions
- structured plan mutation
- question answering about steps
- preserving session state across consecutive edits

Examples it now supports:

- "swap 3 and 4"
- "move the URL check before dedup"
- "remove the last step"
- "add a deduplicate step after step 3"
- "what does step 3 do?"
- "looks good"

## 3. A human-readable planning UX was added

New files:

- [formatter.py](/Users/mozart/Documents/workflow_builder/phase2/chat/formatter.py)
- [repl.py](/Users/mozart/Documents/workflow_builder/phase2/chat/repl.py)

This changed the user experience from:

- raw JSON only

to:

- readable draft plan
- readable clarification prompts
- readable validation issues
- a natural-language prompt for the next user action

The REPL now:

- starts a session
- shows the current planning state
- pauses for user input
- routes that input through the negotiator
- loops until approval or abort

## 4. Startup now launches the conversational UX

Updated file:

- [startup.py](/Users/mozart/Documents/workflow_builder/phase2/startup.py)

Behavior now:

- if running in a TTY and no explicit JSON mode is requested, Phase 2 enters the planning REPL
- if `--json` is passed, it still prints the structured turn
- if `--print-request-payload` is passed, it prints the prepared Bedrock payload instead

This gives both:

- developer-friendly machine output
- user-friendly interactive planning

## 5. Validation remains the guardrail

Even after adding conversational edits, plan mutation is not free-form.

The updated negotiation flow still validates the plan after edits using:

- [validators.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/validators.py)

This matters because the UX should feel conversational, but the resulting plan still needs:

- valid numbering
- schema-compatible chaining
- proper repo vs new tagging
- sensible input bindings

## Bedrock vs Heuristic Path

The current design is intentionally dual-path:

- default: Bedrock Claude-backed intent inference
- fallback: heuristic local intent inference

Why:

- production behavior should rely on Claude for better language understanding
- local development and tests still need to run without external calls
- `rules.md` prevents executing live Bedrock requests in this environment

This means the runtime is now designed for real Bedrock-backed interaction, even though tests still validate the fallback behavior offline.

## What This Solves

These changes solve the original UX gap:

- previously, the system produced a final result immediately
- now, the system can co-plan with the user before final approval

That is the key change from:

- "planner as output generator"

to:

- "planner as conversational collaborator"

## What Is Still Not Finished

This is still planning-only interactivity.

The current back-and-forth session does not yet include:

- task building for `source == "new"` steps
- workflow graph compilation
- workflow execution
- workflow verification
- workflow registry and workflow IDs

Those belong to the next phase of work described in `phase4.md`.

## Summary

The Phase 2 experience has been upgraded from a single-turn JSON response into a genuine planning session by adding:

- intent inference
- stateful plan negotiation
- confirmation-gated edits
- question handling
- a readable planning formatter
- an interactive REPL loop
- Bedrock-first intent inference design with offline fallback

This is the foundation needed before the full Phase 4 execution workflow can feel like a coherent chat session rather than a chain of disconnected commands.
