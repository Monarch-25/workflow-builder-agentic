Story Name: Build the Hybrid Workflow Orchestrator with Tool Search and RAG-Based Plan Proposal
What:

Implement the IntentParser that takes a natural language user query and produces a structured, ordered ProposedPlan (list of TaskStep objects) by combining Titan-powered semantic search with Claude Sonnet's reasoning over discovered tasks
Integrate the Tool Search Tool (tool_search_tool_regex_20251119) so the orchestrator loads task definitions on-demand rather than injecting all 30+ task descriptions into context upfront, reducing token overhead by ~85%
Implement the multi-turn tool use resolution loop: Claude searches for tasks, receives matching tool specs, reasons about fit, and iterates until it produces a complete plan with each step tagged as repo, repo_adapted, or new
Build the GapDetector that separates approved plan steps into existing repo tasks and net-new tasks requiring the Task Builder

Why:

The orchestrator is the first user-facing intelligence in the Workflow Automation Engine MVP — it is what transforms a plain English request into an actionable, structured plan, and its quality directly determines user trust in the system
Using Tool Search instead of full context injection is architecturally critical at this stage: even with 30 seed tasks, loading all definitions upfront costs ~6–8K tokens per orchestration call; at 100+ tasks this becomes prohibitive and must be designed correctly from the start
Correctly tagging steps as repo vs new is the branching condition that determines whether the Task Builder is invoked — an incorrect gap detection directly causes unnecessary task creation or missing functionality
Validating the plan's input/output schema chain at the proposal stage (not just at compile time) surfaces incompatibilities before the user approves, reducing back-and-forth in later phases

Acceptance Criteria:

Given the query "extract all working URLs from a PDF", the orchestrator returns a ProposedPlan containing at minimum: a file upload step, a text extraction step, a URL extraction step, and a URL liveness check step — all tagged repo — without any hardcoding
The Bedrock request payload for the orchestrator call contains defer_loading: true on all non-anchor task tool specs, and only the Tool Search Tool plus 3 anchor tasks appear in the initial context (verifiable via logged token counts or payload inspection)
A query containing a step with no matching repo task (e.g. "parse a SWIFT MT950 reconciliation report") results in at least one TaskStep with source: "new" in the returned plan
GapDetector.detect_gaps() correctly separates a mixed plan into existing and missing lists, and a plan with all repo tasks returns an empty missing list

Artifacts:

orchestrator/intent_parser.py — full IntentParser with Tool Search loop
orchestrator/gap_detector.py — detect_gaps() function
orchestrator/plan_negotiator.py — skeleton (full NL negotiation loop is Story 3)
Unit tests covering: all-repo plan, mixed plan, all-new plan, multi-search iteration