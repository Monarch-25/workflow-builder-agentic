# Phase 1 and Phase 2 Integration

## Purpose

This document defines how the existing Phase 1 infrastructure and the new Phase 2 orchestrator should work together without duplicating responsibilities or destabilizing the repo.

The short version:

- Phase 1 remains the infrastructure and task-repository foundation
- Phase 2 becomes the orchestration and plan-negotiation layer
- Phase 2 should reuse Phase 1 task metadata and repo contracts whenever possible
- Bedrock orchestration should move to `InvokeModel`, but the rest of the system does not need to migrate all at once

## Responsibilities by Phase

### Phase 1 owns

- config conventions and environment variables
- Bedrock model ids and advanced-tool beta settings
- task metadata structure via `AtomicTask`
- local task storage and retrieval
- Redis cache and semantic search plumbing
- seed task inventory

Relevant files:

- [config.py](/Users/mozart/Documents/workflow_builder/phase1/core/config.py)
- [llm.py](/Users/mozart/Documents/workflow_builder/phase1/core/llm.py)
- [schema.py](/Users/mozart/Documents/workflow_builder/phase1/repo/schema.py)
- [local_task_repo.py](/Users/mozart/Documents/workflow_builder/phase1/repo/local_task_repo.py)
- [seed_loader.py](/Users/mozart/Documents/workflow_builder/phase1/seeds/seed_loader.py)

### Phase 2 owns

- clarification-first intent parsing
- orchestration tool-spec compilation
- draft plan generation
- deterministic plan validation
- gap detection
- plan review and revision loop
- orchestration request building for Bedrock `InvokeModel`

Relevant files:

- [config.py](/Users/mozart/Documents/workflow_builder/phase2/core/config.py)
- [llm.py](/Users/mozart/Documents/workflow_builder/phase2/core/llm.py)
- [models.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/models.py)
- [tool_specs.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/tool_specs.py)
- [intent_parser.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/intent_parser.py)
- [validators.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/validators.py)
- [gap_detector.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/gap_detector.py)
- [plan_negotiator.py](/Users/mozart/Documents/workflow_builder/phase2/orchestrator/plan_negotiator.py)

## Integration Contract

Phase 2 should treat Phase 1 as the source of truth for repo tasks.

That means:

- task ids come from `phase1/repo/schema.py`
- task metadata is loaded through the Phase 1 repo contract
- semantic retrieval continues to call `search_similar_tasks(...)`
- task input and output schemas are validated using Phase 1 metadata, not a second schema registry

The key shared contract is `AtomicTask`.

Phase 2 depends on these `AtomicTask` fields being stable:

- `task_id`
- `name`
- `description`
- `input_schema`
- `output_schema`
- `tags`
- `usage_examples`

If any of those change, Phase 2 tool compilation and validation logic must be updated at the same time.

## Transport Boundary

The main architectural split is this:

- Phase 1 `BedrockClaudeLLM` is still `Converse`-centric
- Phase 2 `BedrockClaudeLLM` is `InvokeModel`-first for orchestration

This is intentional.

Why:

- Bedrock Tool Search needs `InvokeModel`
- existing structured-output patterns from Phase 1 do not need to be rewritten immediately
- migration risk is lower if orchestration transport changes are isolated to Phase 2 first

Practical rule:

- use Phase 2 LLM wrapper for orchestrator flows
- keep Phase 1 LLM wrapper for older or compatibility flows until there is a reason to unify them

## Runtime Data Flow

The integrated runtime path should look like this:

1. Startup initializes the Phase 1 repo and seed tasks.
2. Phase 2 receives the user request.
3. Phase 2 loads repo tasks through the Phase 1 repo interface.
4. Phase 2 builds Tool Search-aware tool specs.
5. Phase 2 asks clarification questions if the request is underspecified.
6. Phase 2 retrieves candidate tasks using semantic search and later Bedrock Tool Search.
7. Phase 2 generates a draft plan.
8. Phase 2 validates step-to-step schema compatibility.
9. Phase 2 marks steps as `repo`, `repo_adapted`, or `new`.
10. Phase 2 enters user review and revision.
11. Approved repo-backed steps become input to later execution phases.
12. Missing steps become input to the future Task Builder.

## Current Integration State

Right now the integration is partial but intentional.

Already integrated:

- Phase 2 imports and uses `phase1.repo.schema.AtomicTask`
- Phase 2 expects the Phase 1 repo interface for `get_task`, `list_all_tasks`, and `search_similar_tasks`
- Phase 2 tests load real Phase 1 seed task metadata
- Phase 2 validators use real Phase 1 task schemas to check chaining

Not integrated yet:

- a combined startup path that boots Phase 1 infrastructure and then instantiates the Phase 2 parser
- live Bedrock `InvokeModel` execution inside the parser
- a single user-facing REPL or chat surface spanning both phases

## Recommended Startup Integration

Do not merge the packages yet. Add a thin Phase 2 startup entrypoint first.

Recommended next file:

- `phase2/startup.py`

It should:

1. instantiate `phase2.core.config.Config`
2. initialize Redis and Bedrock clients using the same environment conventions as Phase 1
3. instantiate the Phase 1 `LocalTaskRepo`
4. instantiate the Phase 2 `BedrockClaudeLLM`
5. instantiate `IntentParser`
6. instantiate `PlanNegotiator`
7. expose a minimal CLI or callable function for orchestration-only testing

This keeps the integration explicit and reduces the chance of breaking the stable Phase 1 startup path.

## Shared Config Strategy

Phase 2 currently has its own standalone config class. That is acceptable for now.

Reason:

- it avoids taking a hard dependency on Phase 1's settings implementation
- it keeps the orchestrator testable in environments where the Phase 1 config stack is incomplete

Rule going forward:

- environment variable names shared across phases should remain identical
- new orchestrator-specific settings should live only in Phase 2 until we decide they are globally stable

Examples of shared settings:

- `AWS_REGION`
- `BEDROCK_CLAUDE_MODEL`
- `BEDROCK_ADVANCED_TOOL_BETA`
- `REDIS_HOST`
- `REDIS_PORT`
- `BASE_DIR`

Examples of Phase 2-only settings:

- `ORCHESTRATOR_DEFAULT_TRANSPORT`
- `ORCHESTRATOR_MAX_SEARCH_ROUNDS`
- `ORCHESTRATOR_CANDIDATE_TOP_K`
- `ORCHESTRATOR_TRACE_ENABLED`

## Shared Repo Interface

Phase 2 should continue depending on a narrow repo protocol instead of the full concrete repo class.

Minimum required repo surface:

- `get_task(task_id)`
- `list_all_tasks()`
- `search_similar_tasks(query, top_k=None)`

This is the correct integration boundary because it:

- keeps Phase 2 testable with in-memory repos
- avoids coupling orchestration logic to Redis implementation details
- lets later phases swap retrieval internals without rewriting the parser

## Migration Path to Live Tool Search

The parser currently has a deterministic fallback brain so Phase 2 can be tested offline.

The next integration step should be:

1. keep the current retrieval and validation pipeline
2. add a live Bedrock planner class beside the heuristic one
3. feed the live planner:
   - user request
   - clarification answers
   - compiled tools
   - candidate repo context
4. normalize its output into `ProposedPlan`
5. keep deterministic validation as the final gate

This is important:

- Bedrock planning should generate drafts
- Python validation should still be the acceptance gate before user review

Do not invert that relationship.

## Risks to Avoid

### Duplicating task metadata logic

Do not create a separate Phase 2 task schema. Reuse `AtomicTask`.

### Rebuilding repo access in Phase 2

Do not add a second filesystem or Redis repository layer in Phase 2.

### Mixing transport logic into parser logic

Keep Bedrock request/response formatting in `phase2/core/llm.py`, not inside the parser state machine.

### Skipping deterministic validation

The model can suggest plans, but it should not be the final authority on schema compatibility.

### Merging startup too early

Do not replace `phase1/startup.py` until Phase 2 orchestration is stable enough to deserve being the default entrypoint.

## Suggested Near-Term Integration Tasks

1. Add `phase2/startup.py` that composes the Phase 1 repo with the Phase 2 parser.
2. Add a live Bedrock planning brain that uses the new `InvokeModel` wrapper.
3. Add a small orchestration CLI that prints clarification questions and draft plans.
4. Add integration tests around repo loading plus parser initialization.
5. After those are stable, decide whether a unified root-level startup should replace separate phase entrypoints.
