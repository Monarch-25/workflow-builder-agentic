# Phase 2 Implementation Plan

## Goal

Implement the hybrid workflow orchestrator described in `Implementation_plan/phase2.md`, but make it more robust than the original story by:

- making the orchestration loop clarification-first instead of plan-first
- making Bedrock `InvokeModel` the default path for orchestration so Tool Search is actually available
- preserving Phase 1 as the stable baseline and reusing its repo, embedding, schema, and logging work
- treating semantic search, schema validation, and user clarification as first-class safety rails rather than fallback afterthoughts

## Assumptions

- Phase 1 remains the known-good baseline and should not be destabilized.
- New implementation should live under a new `phase2/` package unless you later choose to fold it back into a shared package.
- We are constrained by `rules.md`: no live Bedrock/Redis execution in this repo, only static implementation, syntax checks, mocks, and payload-shape tests.
- The user wants native Bedrock Tool Search, so `InvokeModel` becomes the default orchestration transport.

## What Phase 1 Already Gives Us

Phase 2 should reuse, not rebuild:

- `phase1/core/llm.py`: Bedrock client wrapper patterns and request logging
- `phase1/core/config.py`: model/beta/logging configuration
- `phase1/repo/local_task_repo.py`: local task storage, Redis cache contract, semantic search entrypoint
- `phase1/repo/schema.py`: `AtomicTask` schema including `usage_examples`
- `phase1/seeds/atomic_tasks/*`: the actual repo tasks the orchestrator must discover and chain

This matters because the orchestrator should be judged on planning quality, not on re-solving repository basics that Phase 1 already completed.

## Critical Architecture Change

The original full-plan pseudocode assumes Tool Search can sit inside the Bedrock `converse()` loop. That is no longer a safe default.

Current Bedrock documentation says the native Tool Search tool is supported through `InvokeModel` / `InvokeModelWithResponseStream`, not the Bedrock `Converse` API. Because of that:

- `InvokeModel` should be the default transport for `phase2/orchestrator/intent_parser.py`
- `Converse` should remain available for compatibility and structured-output paths already built in Phase 1
- the LLM layer should expose both transports behind one interface, with explicit feature flags instead of implicit behavior

## Claude + Bedrock Capability Summary

Capabilities we should plan around:

- Tool Search: available on Bedrock, but use `InvokeModel` as the primary path for orchestration
- Standard tool use: available and should be used for structured plan output and controlled clarifications
- `tool_choice=auto`: preferred for interactive orchestration because Claude can ask clarifying questions before committing to a plan
- Prompt caching: worth adding after the first working slice because the orchestrator will reuse a large stable system prompt and stable anchor tools

Capabilities to avoid depending on for the first Phase 2 slice:

- Anthropic-only assumptions that are not clearly exposed the same way on Bedrock
- code-execution-heavy planning logic inside the model when deterministic Python validation is cheaper and easier to test locally
- any flow that requires live external calls for correctness tests in this repo

## Phase 2 Outcome

By the end of this phase, the orchestrator should be able to:

1. read a natural-language workflow request
2. detect ambiguity and ask targeted follow-up questions before over-planning
3. use Tool Search plus repo semantic search to discover relevant tasks
4. assemble an ordered draft plan with explicit step-to-step input/output compatibility checks
5. mark each step as `repo`, `repo_adapted`, or `new`
6. explain why a step is missing and what additional user input could reduce uncertainty
7. iterate with the user until the plan is approved or abandoned

## Revised Implementation Tracks

### Track 1: Create a Bedrock transport layer that supports both `InvokeModel` and `Converse`

Add `phase2/core/llm.py` with:

- a shared Bedrock wrapper that supports both `invoke_model(...)` and `converse(...)`
- explicit methods such as `invoke_orchestrator(...)` and `invoke_structured(...)`
- request payload logging for both paths
- response normalizers so orchestrator code does not need Bedrock-specific branching everywhere

Key requirement:

- orchestration calls must default to `InvokeModel`
- existing structured output patterns from Phase 1 can remain `Converse`-backed until we decide to migrate them

Why this makes the system more robust:

- it removes the hidden mismatch between the old plan and current Bedrock support
- it isolates transport churn to one file instead of leaking it into the orchestrator loop

### Track 2: Build an orchestrator task-spec compiler optimized for Tool Search

Add `phase2/orchestrator/tool_specs.py` with:

- `build_orchestrator_tools(all_tasks)`
- anchor-task selection rules
- deferred-loading rules for non-anchor tasks
- per-task tool metadata enriched with:
  - description
  - input schema
  - output schema
  - tags
  - usage examples
  - optional search aliases derived from tags and task id tokens

Anchor tasks should be selected deliberately, not hardcoded forever. Initial anchors should likely include:

- `upload_file_v1`
- `return_output_v1`
- `log_error_v1`

Optional fourth anchor if tests justify it:

- `save_to_json_v1`

Why this matters:

- the model needs enough context to reason well, but not so much that every request starts with a bloated prompt
- tags and aliases improve both Tool Search discoverability and semantic fallback quality

### Track 3: Implement a clarification-first `IntentParser`

Add `phase2/orchestrator/intent_parser.py` with a real state machine instead of a single-shot prompt.

Proposed high-level loop:

1. Parse request and classify ambiguity
2. If essential parameters are missing, ask the user 1-3 targeted questions
3. Run one or more Tool Search queries
4. Run local semantic search as a second opinion
5. Merge candidate tasks into a planning context
6. Ask Claude for a draft plan
7. Validate the draft in Python
8. If validation fails, either:
   - repair automatically with another search/planning turn
   - or ask the user a targeted question if the failure is requirement-driven
9. Return a structured `ProposedPlan`

The parser should produce structured states, not just final plans:

- `needs_clarification`
- `searching`
- `draft_plan_ready`
- `validation_failed`
- `awaiting_user_confirmation`
- `approved`
- `aborted`

This is the most important robustness change in the phase. The orchestrator should not pretend certainty when the request is underspecified.

### Track 4: Make the orchestrator explicitly interactive

The old story treated `plan_negotiator.py` as mostly future work. That is too weak for the stated goal. For this phase, we should pull a minimal but real interactive review loop into scope.

Add:

- `phase2/orchestrator/models.py`
- `phase2/orchestrator/plan_negotiator.py`

Define at least these models:

- `ClarificationQuestion`
- `ClarificationSet`
- `TaskStep`
- `ProposedPlan`
- `PlanIssue`
- `PlanRevision`

Behavior requirements:

- clarification questions must be specific and minimal
- questions should ask for missing constraints, not repeat the user request
- the model should explain why it is asking
- plan revisions should preserve accepted steps where possible instead of rebuilding the whole plan every time

Examples of valid clarification prompts:

- "Should the URL liveness check follow redirects, or treat redirects as failures?"
- "Is the PDF always text-based, or do we need OCR support for scanned files?"
- "Do you want only live URLs returned, or a report with both live and dead URLs?"

Examples of bad prompts:

- "Can you clarify your request?"
- "Please provide more details."

### Track 5: Add deterministic validation before the user sees a plan

Add `phase2/orchestrator/validators.py` and `phase2/orchestrator/gap_detector.py`.

Validation should check:

- every step has a valid `source`
- repo steps refer to real task ids
- adjacent step schemas are compatible enough to chain
- a `repo_adapted` step includes a concrete adaptation note
- a `new` step includes a concrete gap explanation
- no plan contains duplicate step numbers or missing step numbers

Gap detection should return more than `existing` and `missing`.

Recommended output shape:

- `existing_steps`
- `adapted_steps`
- `missing_steps`
- `validation_issues`
- `follow_up_questions`

Why this is better:

- `repo_adapted` is operationally different from fully missing
- validation issues should surface early, not be hidden in free-text reasoning

### Track 6: Add search orchestration and fallback behavior

The orchestrator should not trust a single search path.

Implement a hybrid retrieval strategy:

- first pass: Tool Search with short keyword queries
- second pass: local semantic search using `LocalTaskRepo.search_similar_tasks(...)`
- merge pass: dedupe and rerank by relevance, schema fit, and tag overlap

If Tool Search fails or returns weak coverage:

- retry with narrower queries
- retry with broader task-family queries
- compare against semantic search results
- if still weak, ask the user a targeted clarification instead of hallucinating a plan

This gives us graceful degradation if Bedrock tool behavior changes or task metadata is imperfect.

### Track 7: Add observability for planning quality

Add `phase2/orchestrator/tracing.py` or keep this in the parser initially.

Log locally:

- user request
- clarification questions asked
- Tool Search queries issued
- semantic search queries issued
- candidate task ids returned
- discarded tasks and why
- final plan
- validation failures

This is essential because orchestration bugs will be reasoning bugs, not just syntax bugs.

### Track 8: Add tests that reflect real orchestration failure modes

Create `phase2/tests/` with mocked Bedrock responses and local-only fixtures.

Minimum tests:

- all-repo plan for "extract all working URLs from a PDF"
- mixed plan where one step becomes `repo_adapted`
- mixed plan where one step becomes `new`
- ambiguity flow that asks a clarification question before searching
- multi-search iteration where the first search is insufficient
- validation failure caused by schema mismatch between adjacent steps
- Tool Search unavailable, semantic fallback still produces a reasonable draft
- request payload tests showing orchestrator uses `InvokeModel` by default and deferred loading for non-anchor tools

Because `rules.md` forbids live external execution here, these tests should verify:

- request payload shape
- state transitions
- plan validation behavior
- fallback behavior

They should not depend on live Bedrock or Redis.

## Proposed File Layout

```text
phase2/
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── llm.py
├── orchestrator/
│   ├── __init__.py
│   ├── models.py
│   ├── tool_specs.py
│   ├── intent_parser.py
│   ├── validators.py
│   ├── gap_detector.py
│   ├── plan_negotiator.py
│   └── tracing.py
└── tests/
    ├── test_intent_parser.py
    ├── test_gap_detector.py
    ├── test_tool_specs.py
    └── test_negotiator.py
```

## Orchestrator Prompting Strategy

The system prompt should explicitly tell Claude to:

- ask clarifying questions when critical constraints are missing
- prefer repo tasks over inventing new ones
- run multiple short searches instead of one vague search
- explain uncertainty explicitly
- never mark a step as `repo` unless the task actually exists
- never use `repo_adapted` without describing the adaptation
- propose `new` only after retrieval paths are exhausted

The model should also be given structured output schemas for:

- clarification request
- draft plan
- revised plan
- validation-repair response

This keeps the loop inspectable and makes failures easier to test.

## Robustness Improvements Over the Original Story

These changes are deliberate upgrades over `Implementation_plan/phase2.md`:

- `InvokeModel` default instead of assuming Tool Search works through `Converse`
- clarification-first loop instead of immediate plan generation
- hybrid retrieval instead of Tool Search alone
- deterministic schema-chain validation before user review
- real interactive negotiation in this phase instead of postponing it
- plan state machine and traces instead of opaque free-text reasoning
- stronger distinction between `repo_adapted` and `new`

## Delivery Order

Implement in this order:

1. `phase2/core/llm.py`
2. `phase2/orchestrator/models.py`
3. `phase2/orchestrator/tool_specs.py`
4. `phase2/orchestrator/validators.py`
5. `phase2/orchestrator/gap_detector.py`
6. `phase2/orchestrator/intent_parser.py`
7. `phase2/orchestrator/plan_negotiator.py`
8. `phase2/tests/*`

This order forces the transport and schema contracts to stabilize before the planning loop grows complicated.

## Exit Criteria

Phase 2 is done when all of the following are true:

- the orchestrator defaults to `InvokeModel`
- Tool Search tool specs are built with deferred loading for non-anchor tasks
- the parser can stop and ask targeted clarifying questions
- the parser can iterate search -> draft -> validate -> revise
- mixed plans correctly label `repo`, `repo_adapted`, and `new`
- validation issues are surfaced explicitly
- local tests cover ambiguity, retrieval fallback, and payload shape

## Sources

- AWS Bedrock Tool Search on built-in tools: https://docs.aws.amazon.com/bedrock/latest/userguide/built-in-tools-tool-search.html
- AWS Bedrock built-in tools overview: https://docs.aws.amazon.com/bedrock/latest/userguide/built-in-tools.html
- AWS Bedrock prompt caching: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
- Anthropic tool use overview and prompting guidance: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Anthropic prompt engineering for tool use: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/tool-use-prompting
