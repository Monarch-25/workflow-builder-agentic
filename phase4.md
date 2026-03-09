Story Name: Build the Task Builder, Workflow Executor, Graph Registry, and End-to-End REPL
What:

Implement the TaskBuilder — the full creation loop for net-new atomic tasks: LLM approach proposal, Python script generation against the declared tool registry, sandboxed subprocess execution with resource limits, intent-inference-driven user verification, and usage_examples generation before writing the verified task to the local repo
Build the WorkflowGraph, TaskNode, CompiledWorkflow, and ProgrammaticWorkflowRunner — the runtime node graph that dynamically wires verified task scripts into a sequential execution graph using graph.append(node), with schema chain validation at compile time and PTC-based execution for large-data workflows
Implement the WorkflowRegistry with content-addressed SHA IDs, local filesystem persistence, and Redis caching so verified workflows can be stored, retrieved, and shared across users via a short ID
Wire the complete ChatSession REPL state machine — IDLE → PLAN_REVIEW → TASK_BUILD → GRAPH_BUILD → WORKFLOW_VERIFY → DONE — integrating all prior components into a single end-to-end conversation flow from NL query to shared workflow ID

Why:

This story delivers the complete MVP — without the Task Builder, any workflow requiring a capability not in the seed repo is blocked; without the executor, approved plans never actually run; and without the registry, every workflow is ephemeral and cannot be reused or shared
The sandboxed subprocess approach with ulimit resource caps is a non-negotiable security requirement for a banking environment where generated code must be strictly contained before any user shares a workflow ID with colleagues
The content-addressed workflow ID design (SHA of the task list) ensures that two users independently building the same workflow receive the same shareable ID, enabling organic workflow reuse without a deduplication mechanism
Completing the full REPL state machine in this story means the entire system can be demonstrated end-to-end in a single session, which is the key acceptance gate for the Workflow Automation Engine MVP epic

Acceptance Criteria:

Given a plan containing one source: "new" task, the Task Builder generates a Python script, runs it in the sandbox, shows captured stdout/stderr to the user, and on approval stores the task under ~/.workflow_engine/atomic_tasks/ with a valid metadata.json and at least 2 usage examples — all verifiable by a reviewer inspecting the directory
WorkflowGraph.compile() raises a SchemaCompatibilityError when the output schema of node N does not cover the input schema of node N+1, and the error message names the failing task and the missing fields
A full session starting from "extract all working URLs from a PDF" through plan approval, graph compilation, execution on a real PDF, and workflow approval produces a wf_ prefixed ID; a second session running run workflow <id> on the same PDF produces identical live_urls output
A sandboxed script that attempts import subprocess and calls os.system("rm -rf /") is blocked by the resource limits and returns a non-zero exit code with the error captured in SandboxResult.stderr — not a system-level failure

Artifacts:

task_builder/builder.py, task_builder/sandbox.py, task_builder/tool_registry.py, task_builder/verifier.py
executor/graph.py, executor/node_factory.py, executor/runner.py, executor/context.py, executor/programmatic_runner.py
registry/workflow_registry.py, registry/workflow_loader.py
chat/repl.py, chat/formatter.py
End-to-end integration test: full session from NL query → shared workflow ID, runnable by a reviewer with a single python startup.py command