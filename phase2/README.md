# Workflow Engine - Phase 2

## Overview

Phase 2 adds the interactive workflow planning layer on top of the Phase 1 task repo.

It currently includes:

- clarification-first intent parsing
- Tool Search-oriented orchestration request building
- deterministic plan validation and gap detection
- natural-language plan negotiation
- an interactive planning REPL

Phase 2 is planning-focused. It does not yet execute workflows end-to-end.

## Usage

### Interactive Planning Session

Run the planner in interactive mode:

```bash
cd workflow_builder
python phase2/startup.py --request "extract all working URLs from a PDF"
```

When running in a TTY, this starts the conversational planning loop by default.

Expected behavior:

- the system may ask clarification questions first
- it then shows a readable draft plan
- you can respond in natural language
- the system can revise the plan, answer questions, or ask for confirmation
- the session ends when you approve or abort

Examples of valid follow-up messages:

- `looks good`
- `move the URL check before dedup`
- `remove the last step`
- `add a deduplicate step after step 3`
- `what does step 3 do?`
- `abort`

### JSON Output Mode

If you want the raw structured output instead of the interactive session:

```bash
python phase2/startup.py --request "extract all working URLs from a PDF" --json
```

This prints the current `OrchestrationTurn` as JSON.

### Clarification Answers via CLI

You can also answer clarification prompts non-interactively:

```bash
python phase2/startup.py \
  --request "process report" \
  --answer input_artifact=pdf \
  --answer desired_output="live urls only" \
  --json
```

### Print the Prepared Bedrock Payload

To inspect the orchestration request payload without executing the planner loop:

```bash
python phase2/startup.py \
  --request "extract all working URLs from a PDF" \
  --print-request-payload
```

## Bedrock Behavior

Phase 2 uses two LLM paths with different purposes:

- orchestration planning request building defaults to Bedrock `InvokeModel`
- intent inference defaults to Bedrock `Converse` structured output

Intent inference also has a heuristic fallback path for offline tests and local development.

## Notes

- Phase 2 reuses the Phase 1 task repository and seed task metadata.
- In this repo environment, `rules.md` still applies: no live external-service execution should be relied on here.
- The current UX is interactive for planning and negotiation, not for workflow execution yet.

## Verification

```bash
conda run -n mambaGPT python -m unittest discover phase2/tests
conda run -n mambaGPT python -m compileall phase2
```
