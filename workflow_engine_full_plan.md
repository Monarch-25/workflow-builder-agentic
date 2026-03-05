# Workflow Engine — Complete System Plan

---

## System Overview

```
User (Chat/REPL)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                    CHAT INTERFACE LAYER                      │
│         (session mgmt, turn routing, intent inference)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────▼───────────┐
           │  INTENT INFERENCE NODE │  ◄── Sits at EVERY human boundary
           │  (NL → structured     │       Plan review / Task build /
           │   intent via Claude)  │       Workflow verify
           └───────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │  WORKFLOW ORCHESTRATOR │  ◄── Phase 1: Intent → Atomic Task List
           │  Hybrid RAG + LLM     │
           │  (Tool Search Tool)   │
           └───────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │   ATOMIC TASK REPO    │  ◄── Local filesystem (source of truth)
           │  (match / gap detect) │       + Redis VSS (semantic search cache)
           └───────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │     TASK BUILDER      │  ◄── Phase 2: Build & verify missing tasks
           │  (LLM + sandbox exec) │
           └───────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │   WORKFLOW EXECUTOR   │  ◄── Phase 3: Dynamic graph construction
           │ (Programmatic Tool    │       + runtime execution
           │  Calling via Bedrock) │
           └───────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │   WORKFLOW REGISTRY   │  ◄── Verified graphs stored with shared IDs
           │  (local + Redis)      │
           └───────────────────────┘
```

---

## Project Structure

```
workflow_engine/
├── core/
│   ├── session.py              # Chat session + turn state machine
│   ├── llm.py                  # BedrockClaudeLLM wrapper (PTC + Tool Search + beta header)
│   ├── embeddings.py           # Bedrock Titan embedding wrapper
│   ├── intent_infer.py         # IntentInferenceNode — NL → structured intent
│   └── config.py               # All env vars and constants
├── orchestrator/
│   ├── intent_parser.py        # NL → atomic task list (RAG + Tool Search Tool)
│   ├── gap_detector.py         # Identifies tasks missing from repo
│   └── plan_negotiator.py      # User approval loop via IntentInferenceNode
├── repo/
│   ├── local_task_repo.py      # Local filesystem + Redis task CRUD
│   ├── vector_index.py         # Redis VSS index management
│   └── schema.py               # AtomicTask Pydantic model (with usage_examples)
├── task_builder/
│   ├── builder.py              # LLM script generation + iteration loop
│   ├── sandbox.py              # Subprocess sandboxing with resource limits
│   ├── tool_registry.py        # Pre-approved tool declarations for LLM
│   └── verifier.py             # User verification loop via IntentInferenceNode
├── executor/
│   ├── graph.py                # Runtime node graph (sequential wiring)
│   ├── node_factory.py         # Instantiates TaskNode from task metadata + script
│   ├── programmatic_runner.py  # PTC-based execution via Bedrock (context-efficient)
│   ├── runner.py               # Chooses graph vs programmatic runner
│   └── context.py              # Shared in-memory WorkflowContext
├── registry/
│   ├── workflow_registry.py    # Stores verified workflows with shared IDs (local + Redis)
│   └── workflow_loader.py      # Load and run workflow by shared ID
├── seeds/
│   └── atomic_tasks/           # Pre-built scripts for all 30+ seeded tasks
│       ├── extract_text_from_pdf_v1/
│       │   ├── script.py
│       │   └── metadata.json
│       └── ...
├── chat/
│   ├── repl.py                 # Main chat loop — all turns routed via intent inference
│   └── formatter.py            # Pretty print plans, diffs, outputs, tables
├── tools/                      # Pre-approved tool modules (all pre-installed)
│   ├── file_tools.py
│   ├── data_tools.py
│   ├── nlp_tools.py
│   ├── web_tools.py
│   ├── aws_tools.py
│   └── finance_tools.py
├── startup.py                  # Seeds tasks, warms Redis, starts REPL
└── tests/
```

---

## Phase 0: Foundational Infrastructure

### 0.1 Configuration (`core/config.py`)

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Config(BaseSettings):
    # AWS
    AWS_REGION: str = "us-east-1"
    BEDROCK_CLAUDE_MODEL: str = "anthropic.claude-sonnet-4-5"
    BEDROCK_EMBED_MODEL: str  = "amazon.titan-embed-text-v2:0"
    BEDROCK_ADVANCED_TOOL_BETA: str = "advanced-tool-use-2025-11-20"

    # Redis (local instance)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int   = 0

    # Local storage
    BASE_DIR: Path = Path.home() / ".workflow_engine"

    # Repo
    TASK_CACHE_TTL_SEC: int = 86400     # 24h
    VSS_TOP_K: int = 15

    # Sandbox
    SANDBOX_TIMEOUT_SEC: int = 30
    SANDBOX_MAX_MEMORY_MB: int = 512
    SANDBOX_MAX_CPU_SEC: int = 20

    class Config:
        env_file = ".env"
```

### 0.2 Startup Sequence (`startup.py`)

```python
def startup():
    cfg = Config()

    # Ensure local directories exist
    for subdir in ["atomic_tasks", "workflows", "embeddings"]:
        (cfg.BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)

    redis_client   = redis.Redis(cfg.REDIS_HOST, cfg.REDIS_PORT, cfg.REDIS_DB)
    bedrock_client = boto3.client("bedrock-runtime", region_name=cfg.AWS_REGION)

    llm       = BedrockClaudeLLM(bedrock_client, cfg)
    embedder  = TitanEmbedder(bedrock_client, cfg)

    # Ensure VSS index exists in Redis
    ensure_vss_index(redis_client)

    # Warm Redis from local filesystem if cold (first boot or Redis flush)
    repo = LocalTaskRepo(redis_client, embedder, cfg)
    repo.warm_cache_from_local()

    # Seed pre-built tasks from seeds/ if repo is empty
    if redis_client.scard("task:index") == 0:
        seed_atomic_tasks(repo, cfg)

    session = ChatSession(repo, llm, cfg)
    session.run()
```

---

## Phase 0.3: Approved Tool Library for Task Builder

These are all pre-installed in the environment and declared to the LLM as available imports. The task builder never installs packages at runtime — it only uses what is here.

**Category 1 — File & Document Processing**
- `pdfplumber`, `PyMuPDF (fitz)` — PDF text, table, image extraction
- `python-docx`, `openpyxl`, `xlrd` — Word/Excel read/write
- `camelot-py`, `tabula-py` — Table extraction from PDFs (critical for bank statements, filings)
- `pillow`, `pytesseract` — OCR for scanned documents
- `pandas` — `read_excel()`, `read_csv()`, `read_parquet()`, `read_json()`

**Category 2 — Data & Analytics**
- `pandas`, `numpy`, `scipy` — Core analytics
- `polars` — Fast dataframe processing for large datasets
- `duckdb` — In-process SQL on files, parquet, dataframes: `duckdb.sql("SELECT ... FROM 'file.parquet'")`
- `scikit-learn` — Clustering, anomaly detection, regression, preprocessing
- `statsmodels` — Time series, regression, statistical tests
- `great_expectations` — Data quality validation
- `pyjanitor` — Data cleaning utilities

**Category 3 — Financial & Market Data**
- `yfinance` — Market price data
- `pandas-datareader` — FRED, World Bank, Quandl
- `quantlib` — Quantitative finance: pricing, curves, risk
- `pandas-ta` — Technical analysis indicators: RSI, MACD, Bollinger
- `empyrical`, `pyfolio` — Portfolio analytics: Sharpe, drawdown, alpha/beta
- `riskfolio-lib` — Portfolio optimization
- `fredapi` — Federal Reserve Economic Data

**Category 4 — NLP & Text Processing**
- `spacy` — NER, POS tagging, dependency parsing: `spacy.load('en_core_web_sm')`
- `transformers` (HuggingFace, offline models) — Embeddings, classification
- `nltk` — Tokenization, stemming, n-grams
- `rapidfuzz` — Fuzzy string matching for entity reconciliation: `fuzz.ratio(a, b)`
- `langdetect` — Language detection
- `regex` — Advanced PCRE-compatible pattern matching

**Category 5 — Web & Network**
- `httpx` — Sync and async HTTP: `httpx.AsyncClient()` for bulk requests
- `aiohttp` — High-performance async HTTP for bulk URL checking
- `beautifulsoup4`, `lxml` — HTML/XML parsing
- `validators` — `validators.url()`, `validators.email()`, `validators.ip_address()`
- `tenacity` — Retry logic with exponential backoff

**Category 6 — Database & Storage**
- `redis-py` — Redis operations from within task scripts
- `boto3` — All AWS services
- `sqlalchemy`, `psycopg2` — SQL databases
- `duckdb` — In-process analytical SQL (see above)
- `pymongo` — MongoDB

**Category 7 — AWS Services (via boto3)**
- `Textract` — OCR + form/table extraction from document images
- `Comprehend` — Sentiment, entity recognition, PII detection, key phrases
- `Bedrock Runtime` — LLM/embedding calls from within task scripts
- `S3` — File upload/download (available even though primary storage is local)
- `Athena` — SQL over S3 data lakes

**Category 8 — Compliance & Reporting**
- `reportlab`, `weasyprint` — PDF report generation
- `jinja2` — Report/email templating
- `openpyxl` — Styled Excel report generation
- `python-docx` — Word report generation

**Category 9 — Utilities**
- `pydantic` — Data validation and schema enforcement within tasks
- `loguru` — Structured logging
- `tqdm` — Progress tracking for long-running loops
- `hashlib`, `cryptography` — Checksums and encryption
- `jsonpath-ng` — JSONPath expressions
- `xmltodict` — XML ↔ dict conversion
- `arrow` — Timezone-aware datetime handling

---

## Phase 1: Atomic Task Repository

### 1.1 AtomicTask Schema (`repo/schema.py`)

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AtomicTask(BaseModel):
    task_id: str                        # e.g. "extract_text_from_pdf_v1"
    name: str                           # Human label: "Extract Text from PDF"
    description: str                    # What it does — used for RAG embedding
    input_schema: dict                  # {field_name: type_hint} expected inputs
    output_schema: dict                 # {field_name: type_hint} guaranteed outputs
    script_path: str                    # Absolute local path to script.py
    dependencies: list[str]             # pip packages required
    tags: list[str]                     # ["pdf", "text", "extraction"]
    author: str
    created_at: datetime
    verified: bool                      # True only after user sign-off
    version: int
    usage_count: int
    embedding: Optional[list[float]] = None   # Titan embedding of description

    # Tool Use Examples: 1-3 concrete input dicts shown to LLM in tool spec
    # Teaches correct invocation patterns, not just schema
    usage_examples: list[dict] = []
```

### 1.2 Local Filesystem + Redis Storage (`repo/local_task_repo.py`)

**Local directory layout:**
```
~/.workflow_engine/
├── atomic_tasks/
│   ├── extract_text_from_pdf_v1/
│   │   ├── script.py
│   │   └── metadata.json
│   └── ...
├── workflows/
│   ├── wf_3a9f12bc/
│   │   ├── metadata.json
│   │   └── task_list.json
│   └── ...
└── embeddings_snapshot.pkl     ← periodic snapshot for Redis cold-start
```

**Redis key layout:**
```
task:meta:{task_id}     → JSON string of AtomicTask metadata (24h TTL)
task:index              → SET of all task_ids
task:vec:{task_id}      → HASH { embedding: <float32 bytes>, task_id, name, description }
workflow:{workflow_id}  → JSON string of WorkflowRecord (7 day TTL)
workflow:index          → SET of all workflow_ids
```

```python
class LocalTaskRepo:
    def __init__(self, redis_client, embedder, cfg: Config):
        self.redis   = redis_client
        self.embed   = embedder
        self.cfg     = cfg
        self.base    = cfg.BASE_DIR / "atomic_tasks"

    def upsert_task(self, task: AtomicTask, script: str) -> None:
        task_dir = self.base / task.task_id
        task_dir.mkdir(exist_ok=True)
        (task_dir / "script.py").write_text(script)
        (task_dir / "metadata.json").write_text(task.model_dump_json())

        embedding = self.embed(task.description)
        task.embedding = embedding

        # Redis VSS
        self.redis.hset(f"task:vec:{task.task_id}", mapping={
            "task_id":     task.task_id,
            "name":        task.name,
            "description": task.description,
            "embedding":   np.array(embedding, dtype=np.float32).tobytes()
        })
        self.redis.sadd("task:index", task.task_id)
        self.redis.setex(
            f"task:meta:{task.task_id}",
            self.cfg.TASK_CACHE_TTL_SEC,
            task.model_dump_json()
        )

    def get_task(self, task_id: str) -> AtomicTask:
        # Redis cache first
        cached = self.redis.get(f"task:meta:{task_id}")
        if cached:
            return AtomicTask.model_validate_json(cached)
        # Local filesystem fallback
        meta_path = self.base / task_id / "metadata.json"
        task = AtomicTask(**json.loads(meta_path.read_text()))
        self.redis.setex(
            f"task:meta:{task_id}",
            self.cfg.TASK_CACHE_TTL_SEC,
            task.model_dump_json()
        )
        return task

    def get_script(self, task_id: str) -> str:
        return (self.base / task_id / "script.py").read_text()

    def search_similar_tasks(self, query: str, top_k: int = None) -> list[AtomicTask]:
        k = top_k or self.cfg.VSS_TOP_K
        q_vec = np.array(self.embed(query), dtype=np.float32).tobytes()
        results = self.redis.ft("task_vss_idx").search(
            Query(f"*=>[KNN {k} @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("task_id", "name", "description", "score")
            .dialect(2),
            query_params={"vec": q_vec}
        )
        return [self.get_task(r.task_id) for r in results.docs]

    def list_all_tasks(self) -> list[str]:
        return [t.decode() for t in self.redis.smembers("task:index")]

    def warm_cache_from_local(self) -> None:
        """Re-index all local tasks into Redis if cache is cold."""
        if self.redis.scard("task:index") > 0:
            return
        for task_dir in self.base.iterdir():
            meta_path  = task_dir / "metadata.json"
            script_path = task_dir / "script.py"
            if meta_path.exists() and script_path.exists():
                task   = AtomicTask(**json.loads(meta_path.read_text()))
                script = script_path.read_text()
                self.upsert_task(task, script)
```

### 1.3 Redis VSS Index Setup (`repo/vector_index.py`)

```python
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

def ensure_vss_index(redis_client) -> None:
    try:
        redis_client.ft("task_vss_idx").info()
    except Exception:
        schema = (
            TextField("$.task_id",     as_name="task_id"),
            TextField("$.name",        as_name="name"),
            TextField("$.description", as_name="description"),
            VectorField("$.embedding",
                algorithm="HNSW",
                attributes={
                    "TYPE": "FLOAT32",
                    "DIM": 1536,          # Titan embedding dimension
                    "DISTANCE_METRIC": "COSINE",
                    "M": 16,
                    "EF_CONSTRUCTION": 200
                },
                as_name="embedding"
            )
        )
        redis_client.ft("task_vss_idx").create_index(
            schema,
            definition=IndexDefinition(
                prefix=["task:vec:"],
                index_type=IndexType.HASH
            )
        )
```

---

## Phase 2: Bedrock LLM Wrapper with Advanced Tool Use

This is the central infrastructure that enables all three Anthropic advanced tool use features through the Bedrock `converse` API.

### 2.1 BedrockClaudeLLM (`core/llm.py`)

```python
import boto3, json, numpy as np
from typing import Any

class BedrockClaudeLLM:
    def __init__(self, bedrock_client, cfg):
        self.client   = bedrock_client
        self.model_id = cfg.BEDROCK_CLAUDE_MODEL
        self.beta     = cfg.BEDROCK_ADVANCED_TOOL_BETA

    def converse(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        enable_advanced_tools: bool = False
    ) -> dict:
        """
        Core Bedrock converse call.
        Advanced tool use beta header injected via additionalModelRequestFields.
        """
        request = {
            "modelId":        self.model_id,
            "system":         [{"text": system}],
            "messages":       messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if tools:
            request["toolConfig"] = {"tools": tools}
        if enable_advanced_tools:
            # This is how the beta header is passed through Bedrock
            request["additionalModelRequestFields"] = {
                "anthropic_beta": [self.beta]
            }
        return self.client.converse(**request)

    def invoke_structured(
        self,
        system: str,
        messages: list[dict],
        output_schema: type,            # Pydantic model class
        enable_advanced_tools: bool = False
    ) -> Any:
        """
        Force JSON output matching a Pydantic schema using tool use.
        Used everywhere we need structured output from the model.
        """
        schema_tool = [{
            "toolSpec": {
                "name": "structured_output",
                "description": "Return structured data exactly matching the schema.",
                "inputSchema": {"json": output_schema.model_json_schema()}
            }
        }]
        response = self.converse(
            messages=messages,
            system=system,
            tools=schema_tool,
            enable_advanced_tools=enable_advanced_tools
        )
        for block in response["output"]["message"]["content"]:
            if (block.get("toolUse", {}).get("name") == "structured_output"):
                return output_schema.model_validate(block["toolUse"]["input"])
        raise ValueError("Model did not return expected structured output")
```

### 2.2 Titan Embedder (`core/embeddings.py`)

```python
class TitanEmbedder:
    def __init__(self, bedrock_client, cfg):
        self.client   = bedrock_client
        self.model_id = cfg.BEDROCK_EMBED_MODEL

    def __call__(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json"
        )
        return json.loads(response["body"].read())["embedding"]
```

---

## Phase 3: Intent Inference Node

The single most important new component. Replaces all rigid command parsing throughout the system. Sits at every human-in-the-loop boundary.

### 3.1 Intent Types and Schema (`core/intent_infer.py`)

```python
from enum import Enum
from pydantic import BaseModel

class IntentType(Enum):
    # Plan negotiation
    APPROVE          = "approve"
    MODIFY_PLAN      = "modify_plan"      # edit, reorder, add, remove steps
    REJECT_PLAN      = "reject_plan"      # start from scratch

    # Task building
    APPROVE_TASK     = "approve_task"
    MODIFY_TASK      = "modify_task"      # change the script behaviour
    RETEST_TASK      = "retest_task"      # run again with same or new input
    SKIP_TASK        = "skip_task"        # drop this new task from the plan

    # Workflow verification
    APPROVE_WORKFLOW = "approve_workflow"
    MODIFY_WORKFLOW  = "modify_workflow"  # add/remove/replace nodes in the graph
    RERUN_WORKFLOW   = "rerun_workflow"   # run again with different inputs

    # Global — valid in any phase
    QUESTION         = "question"         # user asking something, not commanding
    CLARIFY          = "clarify"          # user wants explanation of current state
    ABORT            = "abort"            # cancel everything, return to idle

class InferredIntent(BaseModel):
    intent_type: IntentType
    confidence: float                     # 0.0 – 1.0
    payload: dict                         # intent-specific structured edits
    user_message_rephrased: str           # what the model understood

PHASE_VALID_INTENTS = {
    "plan_review":      ["APPROVE", "MODIFY_PLAN", "REJECT_PLAN",
                         "QUESTION", "CLARIFY", "ABORT"],
    "task_build":       ["APPROVE_TASK", "MODIFY_TASK", "RETEST_TASK",
                         "SKIP_TASK", "QUESTION", "ABORT"],
    "workflow_verify":  ["APPROVE_WORKFLOW", "MODIFY_WORKFLOW",
                         "RERUN_WORKFLOW", "QUESTION", "ABORT"],
}

# Intents where we echo understanding back to the user before acting
CONFIRM_REQUIRED = {
    IntentType.MODIFY_PLAN,
    IntentType.REJECT_PLAN,
    IntentType.MODIFY_WORKFLOW,
    IntentType.ABORT
}
```

### 3.2 IntentInferenceNode

```python
INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a workflow building system used by banking analysts.
Understand what the user wants to do at the current phase of the workflow building process.
Return ONLY a JSON object matching the InferredIntent schema.
Be lenient — users are technical but type casually and often abbreviate.
"""

INTENT_INFERENCE_PROMPT = """
CURRENT PHASE: {phase}

CURRENT STATE:
{current_state}

VALID INTENTS FOR THIS PHASE:
{valid_intents}

USER MESSAGE:
"{user_message}"

Classify the user's intent. If modifying, extract the specific changes as structured
edits in the payload. Be precise.

Payload examples for MODIFY_PLAN:
  "move step 3 after step 5"
    → {{"action": "reorder", "from_step": 3, "to_after_step": 5}}
  "add a dedup step after the URL extraction"
    → {{"action": "add", "after_step": 3, "description": "deduplicate URL list"}}
  "remove the failure analysis"
    → {{"action": "remove", "step_description": "analyze failure reasons"}}
  "swap 2 and 3"
    → {{"action": "swap", "step_a": 2, "step_b": 3}}

Payload examples for MODIFY_TASK:
  "output should be a flat list not a nested dict"
    → {{"feedback": "return a flat list of URLs, not a nested dict"}}
  "handle None inputs gracefully"
    → {{"feedback": "add null checks for all inputs before processing"}}

Payload examples for RETEST_TASK:
  "retest with a PDF that has no URLs"
    → {{"new_test_input": {{"file_path": "/tmp/no_urls.pdf"}}}}
  "run it again"
    → {{}}

Return valid JSON only. No prose.
"""

class IntentInferenceNode:
    def __init__(self, llm: BedrockClaudeLLM):
        self.llm = llm

    def infer(
        self,
        user_message: str,
        phase: str,
        current_state: Any,
        conversation_history: list[dict]
    ) -> InferredIntent:
        prompt = INTENT_INFERENCE_PROMPT.format(
            phase=phase,
            current_state=json.dumps(current_state, indent=2),
            user_message=user_message,
            valid_intents=PHASE_VALID_INTENTS.get(phase, [])
        )
        return self.llm.invoke_structured(
            system=INTENT_SYSTEM_PROMPT,
            messages=conversation_history + [{"role": "user", "content": prompt}],
            output_schema=InferredIntent
        )
```

---

## Phase 4: Workflow Orchestrator

### 4.1 Tool Search Tool Setup (`orchestrator/intent_parser.py`)

The orchestrator uses the **Tool Search Tool** so Claude only loads the task definitions it actually needs, avoiding 20K+ token overhead from injecting all task descriptions upfront.

```python
def build_orchestrator_tools(all_tasks: list[AtomicTask]) -> list[dict]:
    """
    Build the tool list for the orchestrator Claude call.

    Architecture:
    - Tool Search Tool (regex): always loaded (~500 tokens)
    - Code Execution Tool: always loaded
    - 3–5 foundational tasks: always loaded (high-use anchors)
    - All other tasks: defer_loading=True (loaded only when searched)

    This keeps initial context to ~3K tokens vs ~20K+ if all tasks were loaded.
    """
    tools = []

    # 1. Tool Search Tool — always loaded, enables on-demand task discovery
    tools.append({
        "toolSpec": {
            "type": "tool_search_tool_regex_20251119",
            "name": "tool_search_tool_regex"
        }
    })

    # 2. Code Execution — for programmatic orchestration logic
    tools.append({
        "toolSpec": {
            "type": "code_execution_20250825",
            "name": "code_execution"
        }
    })

    # 3. Always-loaded anchors — the 3 tasks present in almost every workflow
    always_loaded = {"upload_file_v1", "return_output_v1", "log_error_v1"}

    for task in all_tasks:
        tool_entry = {
            "toolSpec": {
                "name": task.task_id,
                "description": task.description,
                "inputSchema": {"json": task.input_schema},
            }
        }
        # Tool Use Examples: concrete usage patterns help model invoke correctly
        if task.usage_examples:
            tool_entry["toolSpec"]["input_examples"] = task.usage_examples

        # Defer all non-anchor tasks — they only load when searched for
        if task.task_id not in always_loaded:
            tool_entry["defer_loading"] = True

        tools.append(tool_entry)

    return tools
```

### 4.2 Intent Parser — Hybrid RAG + Tool Search

```python
ORCHESTRATOR_SYSTEM = """
You are a workflow planning assistant for a banking analytics platform.
You have access to a library of atomic tasks discoverable via tool_search_tool_regex.

Your process:
1. Search for tasks relevant to the user's request using the tool search tool.
   Use multiple short targeted searches (e.g. "pdf extract", "url check", "http liveness").
2. Review what's found. Search again with different keywords if you need more options.
3. Use code_execution to build and validate the ordered task list programmatically.
4. Identify any steps that NO existing task covers — mark these as new (gap).
5. Return a structured plan JSON.

Rules for the plan:
- Each task must have ONE clear input and ONE clear output.
- The output of task N must be compatible with the input of task N+1.
- Prefer repo tasks. Only propose NEW tasks when no repo task covers a step.
- Mark each task: source "repo", "repo_adapted" (close but note the gap), or "new".

Available task categories (for search):
file_io, text_extraction, url_processing, data_transform,
financial_analysis, nlp, web_network, validation, reporting
"""

class ProposedPlan(BaseModel):
    task_list: list[TaskStep]
    reasoning: str

class TaskStep(BaseModel):
    step: int
    task_id: Optional[str]      # None if source == "new"
    name: str
    description: str
    source: str                 # "repo" | "repo_adapted" | "new"
    gap_notes: Optional[str]    # only for repo_adapted/new

class IntentParser:
    def __init__(self, llm: BedrockClaudeLLM, repo: LocalTaskRepo):
        self.llm  = llm
        self.repo = repo

    def parse(self, user_query: str) -> ProposedPlan:
        all_tasks = [self.repo.get_task(tid) for tid in self.repo.list_all_tasks()]
        tools     = build_orchestrator_tools(all_tasks)

        messages = [{"role": "user", "content": user_query}]

        # Multi-turn tool use loop: model searches, discovers, then returns plan
        while True:
            response = self.llm.converse(
                messages=messages,
                system=ORCHESTRATOR_SYSTEM,
                tools=tools,
                enable_advanced_tools=True       # activates Tool Search + PTC beta
            )

            stop_reason = response["stopReason"]
            content     = response["output"]["message"]["content"]
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                # Extract structured plan from final text block
                for block in content:
                    if "text" in block:
                        return self._extract_plan(block["text"])
                break

            elif stop_reason == "tool_use":
                tool_results = []
                for block in content:
                    if "toolUse" not in block:
                        continue
                    tool_name   = block["toolUse"]["name"]
                    tool_use_id = block["toolUse"]["toolUseId"]
                    tool_input  = block["toolUse"]["input"]

                    if tool_name == "tool_search_tool_regex":
                        # Tool Search: return matching task tool specs for the query
                        matches = self.repo.search_similar_tasks(
                            tool_input.get("query", ""), top_k=8
                        )
                        result_content = [
                            {
                                "toolSpec": {
                                    "name": t.task_id,
                                    "description": t.description,
                                    "inputSchema": {"json": t.input_schema},
                                    "input_examples": t.usage_examples
                                }
                            }
                            for t in matches
                        ]
                    else:
                        result_content = [{"text": "Tool executed."}]

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": result_content
                        }
                    })
                messages.append({"role": "user", "content": tool_results})

        return ProposedPlan(task_list=[], reasoning="Failed to produce plan.")

    def _extract_plan(self, text: str) -> ProposedPlan:
        # Parse JSON plan from model's final response
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return ProposedPlan.model_validate_json(match.group())
        raise ValueError("Could not extract structured plan from model response")
```

### 4.3 Gap Detector (`orchestrator/gap_detector.py`)

```python
def detect_gaps(
    approved_plan: list[TaskStep]
) -> tuple[list[TaskStep], list[TaskStep]]:
    existing = [t for t in approved_plan if t.source in ("repo", "repo_adapted")]
    missing  = [t for t in approved_plan if t.source == "new"]
    return existing, missing
```

### 4.4 Plan Negotiator (`orchestrator/plan_negotiator.py`)

The negotiator uses the IntentInferenceNode at every turn — no rigid commands.

```python
class PlanNegotiator:
    def __init__(self, llm: BedrockClaudeLLM, intent_node: IntentInferenceNode):
        self.llm         = llm
        self.intent_node = intent_node

    def run(
        self,
        proposed_plan: list[TaskStep],
        session: ChatSession
    ) -> list[TaskStep]:
        history = []

        while True:
            session.display_plan(proposed_plan)
            print("\nDoes this plan look right? Tell me in your own words.")
            user_input = input(">> ").strip()

            intent = self.intent_node.infer(
                user_message=user_input,
                phase="plan_review",
                current_state={"plan": [t.model_dump() for t in proposed_plan]},
                conversation_history=history
            )
            history.append({"role": "user",      "content": user_input})

            # For significant changes, echo understanding before acting
            if intent.confidence < 0.85 or intent.intent_type in CONFIRM_REQUIRED:
                print(f"[SYSTEM] Understood: {intent.user_message_rephrased}")

            if intent.intent_type == IntentType.APPROVE:
                print("[PLAN APPROVED]")
                return proposed_plan

            elif intent.intent_type == IntentType.MODIFY_PLAN:
                proposed_plan = self._apply_plan_edit(
                    proposed_plan, intent.payload, history
                )

            elif intent.intent_type == IntentType.REJECT_PLAN:
                print("[PLAN REJECTED] Starting fresh — please rephrase your request.")
                return None

            elif intent.intent_type == IntentType.QUESTION:
                answer = self._answer_question(user_input, proposed_plan)
                print(f"[ANSWER] {answer}")
                history.append({"role": "assistant", "content": answer})

            elif intent.intent_type == IntentType.ABORT:
                print("[ABORTED]")
                return None

    def _apply_plan_edit(
        self,
        plan: list[TaskStep],
        payload: dict,
        history: list[dict]
    ) -> list[TaskStep]:
        """Send current plan + edit payload to Claude, get back updated plan."""
        prompt = f"""
        Current plan:
        {json.dumps([t.model_dump() for t in plan], indent=2)}

        Edit instruction (structured):
        {json.dumps(payload, indent=2)}

        Apply this edit and return the complete updated plan as JSON.
        Maintain step numbering starting from 1.
        """
        updated = self.llm.invoke_structured(
            system="You are a workflow plan editor. Apply the edit exactly.",
            messages=history + [{"role": "user", "content": prompt}],
            output_schema=ProposedPlan
        )
        return updated.task_list
```

---

## Phase 5: Task Builder

For each task with `source == "new"` in the approved plan, the Task Builder runs a full creation loop.

### 5.1 Builder Loop (`task_builder/builder.py`)

```
[1] Propose approach to user
    Plain English: "Here's how I'll implement 'analyze_url_failure_reasons'..."
    User confirms or redirects — intent inference handles their response.

[2] On approval → Generate Python script via Claude Sonnet
    Prompt includes task spec + full tool registry

[3] Sandbox execution
    Subprocess with resource limits, captured stdout/stderr, timeout

[4] Show output to user
    User responds in natural language — intent inference classifies:
    APPROVE_TASK / MODIFY_TASK / RETEST_TASK / SKIP_TASK

[5a] MODIFY_TASK → extract feedback, regenerate script → back to [3]
[5b] RETEST_TASK → run again with same or new test input → back to [4]
[5c] APPROVE_TASK → generate usage_examples → store in repo
[5d] SKIP_TASK   → remove this step from the plan, continue
```

```python
class TaskBuilder:
    def __init__(self, llm, sandbox, intent_node: IntentInferenceNode, repo):
        self.llm         = llm
        self.sandbox     = sandbox
        self.intent_node = intent_node
        self.repo        = repo

    def build(self, task_step: TaskStep, session: ChatSession) -> AtomicTask | None:
        print(f"\n{'━'*60}")
        print(f"TASK BUILDER: {task_step.name}")
        print(f"{'━'*60}")

        # Step 1: Propose approach
        approach = self._propose_approach(task_step)
        print(f"\n[APPROACH]\n{approach}")
        print("\nShall I proceed? Tell me or suggest changes.")
        user_input = input(">> ").strip()

        intent = self.intent_node.infer(
            user_message=user_input,
            phase="task_build",
            current_state={"task": task_step.model_dump(), "approach": approach},
            conversation_history=[]
        )
        if intent.intent_type == IntentType.SKIP_TASK:
            print(f"[SKIPPED] {task_step.name}")
            return None
        if intent.intent_type == IntentType.MODIFY_TASK:
            task_step.description += f" | User note: {intent.payload.get('feedback','')}"

        # Step 2: Generate script
        script = self._generate_script(task_step)
        test_input = self._generate_test_input(task_step)
        history = []

        while True:
            # Step 3: Sandbox execution
            print(f"\n[SANDBOX] Running...")
            result = self.sandbox.run(script, test_input)

            # Step 4: Show output
            print(f"\n[OUTPUT]\n{result.stdout or '(no stdout)'}")
            if result.stderr:
                print(f"[STDERR]\n{result.stderr}")
            if result.output:
                print(f"[RESULT]\n{json.dumps(result.output, indent=2)}")

            print("\nIs this correct? Tell me what you think.")
            user_input = input(">> ").strip()
            history.append({"role": "user", "content": user_input})

            intent = self.intent_node.infer(
                user_message=user_input,
                phase="task_build",
                current_state={
                    "task":    task_step.model_dump(),
                    "script":  script,
                    "output":  result.output,
                    "stdout":  result.stdout,
                    "stderr":  result.stderr
                },
                conversation_history=history
            )

            if intent.intent_type == IntentType.APPROVE_TASK:
                break
            elif intent.intent_type == IntentType.MODIFY_TASK:
                feedback = intent.payload.get("feedback", user_input)
                script   = self._regenerate_script(script, feedback, history)
            elif intent.intent_type == IntentType.RETEST_TASK:
                if intent.payload.get("new_test_input"):
                    test_input = intent.payload["new_test_input"]
                # else re-run with existing test_input
            elif intent.intent_type == IntentType.SKIP_TASK:
                return None

        # Step 5c: Generate usage_examples, store task
        usage_examples = self._generate_usage_examples(task_step, script)
        task = AtomicTask(
            task_id=f"{task_step.name.lower().replace(' ','_')}_v1",
            name=task_step.name,
            description=task_step.description,
            input_schema=task_step.input_schema or {},
            output_schema=task_step.output_schema or {},
            script_path=str(self.repo.base / f"{task_step.name}_v1" / "script.py"),
            dependencies=[],
            tags=[],
            author="system",
            created_at=datetime.now(),
            verified=True,
            version=1,
            usage_count=0,
            usage_examples=usage_examples
        )
        self.repo.upsert_task(task, script)
        print(f"\n[REPO] Task '{task.task_id}' stored and indexed.")
        return task
```

### 5.2 Standard Script Template

Every LLM-generated task script follows this contract. The LLM fills in `execute()` and any helpers only.

```python
# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       {task_id}
# input_schema:  {input_schema}
# output_schema: {output_schema}

import json, sys
from pathlib import Path

# ─── USER SCRIPT START ────────────────────────────────────────────────────────

{user_generated_code}

# ─── USER SCRIPT END ──────────────────────────────────────────────────────────

def execute(inputs: dict) -> dict:
    # This is the ONLY required entry point.
    # Read from inputs dict, return outputs dict.
    # LLM fills this in.
    ...

if __name__ == "__main__":
    input_path  = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path)  as f: inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f: json.dump(result, f)
```

### 5.3 Sandbox (`task_builder/sandbox.py`)

```python
import subprocess, tempfile, os, resource, json
from dataclasses import dataclass

@dataclass
class SandboxResult:
    stdout:     str
    stderr:     str
    returncode: int
    output:     dict | None

def run_sandboxed(
    script: str,
    input_data: dict,
    timeout: int = 30,
    max_memory_mb: int = 512,
    max_cpu_sec: int = 20
) -> SandboxResult:

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "task_script.py")
        input_path  = os.path.join(tmpdir, "input.json")
        output_path = os.path.join(tmpdir, "output.json")

        with open(script_path, "w") as f: f.write(script)
        with open(input_path,  "w") as f: json.dump(input_data, f)

        def set_limits():
            resource.setrlimit(resource.RLIMIT_CPU,
                (max_cpu_sec, max_cpu_sec))
            resource.setrlimit(resource.RLIMIT_AS,
                (max_memory_mb * 1024 * 1024, max_memory_mb * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_FSIZE,
                (50 * 1024 * 1024, 50 * 1024 * 1024))   # 50MB max file writes

        proc = subprocess.run(
            ["python3", script_path, input_path, output_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=set_limits,
            cwd=tmpdir
        )

        output = None
        if os.path.exists(output_path):
            with open(output_path) as f:
                output = json.load(f)

        return SandboxResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            output=output
        )
```

### 5.4 Tool Registry (`task_builder/tool_registry.py`)

Injected into the Claude prompt for script generation. Declarations only — no runtime install.

```python
TOOL_REGISTRY_PROMPT = """
AVAILABLE TOOLS (all pre-installed, import directly — do NOT pip install):

FILE & DOCUMENT:
  import pdfplumber                    # pdfplumber.open(path) → pages, text, tables
  import fitz                          # PyMuPDF: fitz.open(path) → fine-grained PDF
  import camelot                       # camelot.read_pdf(path, flavor='lattice') → TableList
  import pytesseract                   # pytesseract.image_to_string(PIL.Image) → str
  import openpyxl                      # openpyxl.load_workbook(path)
  import pandas as pd                  # pd.read_excel(), read_csv(), read_parquet()

DATA & ANALYTICS:
  import pandas as pd
  import numpy as np
  import polars as pl                  # Faster: pl.read_csv(), pl.DataFrame
  import duckdb                        # duckdb.sql("SELECT * FROM 'file.parquet'")
  from sklearn.ensemble import ...     # IsolationForest, RandomForest, etc.
  from sklearn.preprocessing import ...
  import statsmodels.api as sm         # OLS, ARIMA, etc.

FINANCIAL:
  import yfinance as yf                # yf.download(ticker, start=, end=)
  import pandas_ta as ta               # df.ta.rsi(), df.ta.macd()
  import empyrical                     # empyrical.sharpe_ratio(returns, ...)
  from fredapi import Fred             # Fred(api_key=...).get_series('GDP')
  import quantlib as ql                # Pricing, curves, risk

NLP & TEXT:
  import spacy                         # nlp = spacy.load('en_core_web_sm')
  from transformers import pipeline    # pipeline('ner'), pipeline('sentiment')
  from rapidfuzz import fuzz           # fuzz.ratio(a, b), fuzz.partial_ratio(a, b)
  import langdetect                    # langdetect.detect(text) → 'en'
  import regex                         # Drop-in re replacement with advanced features

WEB & NETWORK:
  import httpx                         # httpx.get(url), httpx.AsyncClient()
  import aiohttp                       # aiohttp.ClientSession() for async bulk
  from bs4 import BeautifulSoup        # BeautifulSoup(html, 'lxml')
  import validators                    # validators.url(u), validators.email(e)
  from tenacity import retry, stop_after_attempt

AWS:
  import boto3
  # Textract:   boto3.client('textract').detect_document_text(Document=...)
  # Comprehend: boto3.client('comprehend').detect_entities(Text=..., LanguageCode='en')
  # Bedrock:    boto3.client('bedrock-runtime').invoke_model(...)

UTILITIES:
  from pydantic import BaseModel       # Input/output validation within tasks
  import duckdb                        # SQL on any file format
  from jinja2 import Template          # Report templating
  import arrow                         # arrow.now(), .format(), timezone-aware datetimes
  from loguru import logger            # logger.info(), logger.warning()
  import hashlib                       # hashlib.sha256(data).hexdigest()

RULES FOR GENERATED SCRIPTS:
  - Never use os.system(), subprocess, eval(), or exec()
  - Never write files outside /tmp
  - Never make network calls unless the task explicitly requires it
  - The execute(inputs: dict) -> dict function is mandatory
  - All imports must come from the list above
"""
```

---

## Phase 6: Workflow Executor

### 6.1 Shared Context (`executor/context.py`)

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class WorkflowContext:
    """
    In-memory shared state passed between nodes.
    Each node reads inputs from ctx.get() and writes outputs via ctx.set().
    """
    data:   dict      = field(default_factory=dict)
    logs:   list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def set(self, key: str, value: Any):  self.data[key] = value
    def get(self, key: str) -> Any:       return self.data.get(key)
    def log(self, msg: str):              self.logs.append(msg); print(f"  {msg}")
```

### 6.2 Task Node (`executor/node_factory.py`)

```python
class TaskNode:
    def __init__(self, task: AtomicTask, script_content: str):
        self.task = task
        # Compile verified script into namespace (safe — script is already user-verified)
        self._namespace = {}
        exec(
            compile(script_content, task.task_id, 'exec'),
            self._namespace
        )

    def run(self, ctx: WorkflowContext) -> WorkflowContext:
        ctx.log(f"[{self.task.name}] starting")
        # Map context → task inputs
        inputs = {k: ctx.get(k) for k in self.task.input_schema.keys()}
        try:
            outputs = self._namespace['execute'](inputs)
            for k, v in outputs.items():
                ctx.set(k, v)
            ctx.log(f"[{self.task.name}] ✓  outputs: {list(outputs.keys())}")
        except Exception as e:
            ctx.errors.append(f"[{self.task.name}] ERROR: {e}")
            raise
        return ctx


def build_node(task_id: str, repo: LocalTaskRepo) -> TaskNode:
    task   = repo.get_task(task_id)
    script = repo.get_script(task_id)
    return TaskNode(task, script)
```

### 6.3 Workflow Graph (`executor/graph.py`)

```python
class SchemaCompatibilityError(Exception):
    pass

class WorkflowGraph:
    def __init__(self):
        self.nodes: list[TaskNode] = []

    def append(self, node: TaskNode):
        self.nodes.append(node)

    def compile(self) -> 'CompiledWorkflow':
        # Validate output → input schema chaining across all adjacent nodes
        for i in range(len(self.nodes) - 1):
            current_out = set(self.nodes[i].task.output_schema.keys())
            next_in     = set(self.nodes[i+1].task.input_schema.keys())
            missing = next_in - current_out
            if missing:
                raise SchemaCompatibilityError(
                    f"Task '{self.nodes[i+1].task.name}' expects {missing} "
                    f"but prior task only provides {current_out}"
                )
        return CompiledWorkflow(self.nodes)


class CompiledWorkflow:
    def __init__(self, nodes: list[TaskNode]):
        self.nodes = nodes

    def run(self, initial_inputs: dict) -> WorkflowContext:
        ctx = WorkflowContext()
        for k, v in initial_inputs.items():
            ctx.set(k, v)
        for node in self.nodes:
            ctx = node.run(ctx)      # sequential — each node mutates shared context
        return ctx
```

### 6.4 Runner (`executor/runner.py`)

```python
def build_and_run_workflow(
    task_list: list[TaskStep],
    initial_inputs: dict,
    repo: LocalTaskRepo
) -> tuple[CompiledWorkflow, WorkflowContext]:

    graph = WorkflowGraph()

    # Core dynamic assembly — no codegen, just node wiring
    for task_step in task_list:
        node = build_node(task_step.task_id, repo)
        graph.append(node)           # [graph.append(task) for task in task_list]

    compiled = graph.compile()       # schema chain validation
    ctx      = compiled.run(initial_inputs)
    return compiled, ctx
```

### 6.5 Programmatic Tool Calling Runner (`executor/programmatic_runner.py`)

For workflows with large intermediate data (e.g. processing thousands of rows or hundreds of URLs), the PTC runner keeps intermediate results out of Claude's context — only the final output is returned.

```python
class ProgrammaticWorkflowRunner:
    """
    Uses Bedrock Programmatic Tool Calling to orchestrate the workflow.
    Claude writes async Python to call each task; intermediate results
    stay in the code execution sandbox, not in Claude's context.
    """
    def __init__(self, llm: BedrockClaudeLLM, repo: LocalTaskRepo):
        self.llm  = llm
        self.repo = repo

    def _build_ptc_tools(self, task_list: list[TaskStep]) -> list[dict]:
        tools = [{
            "toolSpec": {
                "type": "code_execution_20250825",
                "name": "code_execution"
            }
        }]
        for step in task_list:
            task = self.repo.get_task(step.task_id)
            tools.append({
                "toolSpec": {
                    "name":        task.task_id,
                    "description": task.description,
                    "inputSchema": {"json": task.input_schema},
                    "input_examples": task.usage_examples
                },
                # opt this task into programmatic calling from code_execution
                "allowed_callers": ["code_execution_20250825"]
            })
        return tools

    def run(
        self,
        task_list: list[TaskStep],
        initial_inputs: dict
    ) -> WorkflowContext:
        tools  = self._build_ptc_tools(task_list)
        steps  = "\n".join(
            f"  # Step {i+1}: {s.name}\n  result_{i} = await {s.task_id}(ctx)"
            for i, s in enumerate(task_list)
        )
        prompt = f"""
        Write an async Python orchestration script that executes this workflow.
        Use asyncio.gather() for any steps that can safely run in parallel.
        Keep intermediate data in local variables — only print the final result.

        Steps:
        {steps}

        Initial inputs: {json.dumps(initial_inputs)}

        Rules:
        - Filter/aggregate large intermediate datasets before assigning to ctx
        - Print final output as a single JSON object to stdout
        """

        messages = [{"role": "user", "content": prompt}]
        ctx = WorkflowContext()

        while True:
            response = self.llm.converse(
                messages=messages,
                system="You are a workflow executor. Write efficient async orchestration.",
                tools=tools,
                enable_advanced_tools=True
            )

            stop_reason = response["stopReason"]
            content     = response["output"]["message"]["content"]
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                for block in content:
                    if block.get("toolResult", {}).get("name") == "code_execution":
                        stdout = block["toolResult"]["content"].get("stdout", "")
                        ctx.set("final_output", json.loads(stdout))
                break

            elif stop_reason == "tool_use":
                tool_results = []
                for block in content:
                    if "toolUse" not in block:
                        continue
                    tool_use    = block["toolUse"]
                    tool_id     = tool_use["toolUseId"]
                    tool_name   = tool_use["name"]
                    tool_input  = tool_use["input"]
                    caller      = tool_use.get("caller")

                    # PTC: result goes back to sandbox, not to Claude's context
                    if caller and caller["type"] == "code_execution_20250825":
                        result = run_sandboxed(
                            self.repo.get_script(tool_name), tool_input
                        )
                        tool_results.append({
                            "toolResult": {
                                "toolUseId": tool_id,
                                "content": [{"json": result.output or {}}]
                            }
                        })
                    else:
                        result = run_sandboxed(
                            self.repo.get_script(tool_name), tool_input
                        )
                        tool_results.append({
                            "toolResult": {
                                "toolUseId": tool_id,
                                "content": [{"json": result.output or {}}]
                            }
                        })

                messages.append({"role": "user", "content": tool_results})

        return ctx
```

---

## Phase 7: Workflow Registry

### 7.1 WorkflowRecord Schema

```python
@dataclass
class WorkflowRecord:
    workflow_id:   str            # e.g. "wf_a3f9b2c1"
    name:          str            # User-given or auto-generated name
    description:   str            # Original NL query that produced this workflow
    task_list:     list[str]      # Ordered list of task_ids
    input_schema:  dict           # First task's input_schema
    output_schema: dict           # Last task's output_schema
    author:        str
    created_at:    datetime
    verified:      bool
    run_count:     int
    tags:          list[str]
```

### 7.2 WorkflowRegistry (`registry/workflow_registry.py`)

```python
class WorkflowRegistry:
    def __init__(self, redis_client, cfg: Config):
        self.redis   = redis_client
        self.cfg     = cfg
        self.base    = cfg.BASE_DIR / "workflows"
        self.base.mkdir(exist_ok=True)

    def store(self, record: WorkflowRecord) -> str:
        # Content-addressed ID: same task list → same ID (natural dedup)
        wf_id = "wf_" + hashlib.sha256(
            json.dumps(record.task_list).encode()
        ).hexdigest()[:8]
        record.workflow_id = wf_id

        wf_dir = self.base / wf_id
        wf_dir.mkdir(exist_ok=True)
        (wf_dir / "metadata.json").write_text(
            json.dumps(dataclasses.asdict(record), default=str)
        )

        # Redis cache (7 day TTL)
        self.redis.setex(
            f"workflow:{wf_id}",
            604800,
            json.dumps(dataclasses.asdict(record), default=str)
        )
        self.redis.sadd("workflow:index", wf_id)
        return wf_id

    def load(self, wf_id: str) -> WorkflowRecord:
        cached = self.redis.get(f"workflow:{wf_id}")
        if cached:
            return WorkflowRecord(**json.loads(cached))
        meta_path = self.base / wf_id / "metadata.json"
        return WorkflowRecord(**json.loads(meta_path.read_text()))

    def run_by_id(
        self,
        wf_id: str,
        inputs: dict,
        repo: LocalTaskRepo
    ) -> WorkflowContext:
        record     = self.load(wf_id)
        task_steps = [
            TaskStep(step=i+1, task_id=tid, name=tid,
                     description="", source="repo")
            for i, tid in enumerate(record.task_list)
        ]
        _, ctx = build_and_run_workflow(task_steps, inputs, repo)
        # Increment run count
        record.run_count += 1
        self.store(record)
        return ctx

    def list_all(self) -> list[str]:
        return [wf_id.decode() for wf_id in self.redis.smembers("workflow:index")]
```

---

## Phase 8: Chat Interface (REPL)

### 8.1 Session State Machine

```python
from enum import Enum

class SessionState(Enum):
    IDLE              = "idle"
    PLAN_REVIEW       = "plan_review"
    TASK_BUILD        = "task_build"
    TASK_VERIFY       = "task_verify"
    GRAPH_BUILD       = "graph_build"
    WORKFLOW_VERIFY   = "workflow_verify"
    DONE              = "done"
```

### 8.2 ChatSession (`chat/repl.py`)

```python
class ChatSession:
    def __init__(self, repo, llm, cfg):
        self.repo         = repo
        self.llm          = llm
        self.cfg          = cfg
        self.state        = SessionState.IDLE
        self.intent_node  = IntentInferenceNode(llm)
        self.history      = []              # Full conversation for multi-turn context
        self.proposed_plan: list[TaskStep] = []
        self.approved_plan: list[TaskStep] = []
        self.built_tasks:   dict[str, AtomicTask] = {}
        self.workflow:      WorkflowRecord | None = None

    def run(self):
        print(WELCOME_BANNER)
        while True:
            try:
                user_input = input(">> ").strip()
                if not user_input: continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    print("Goodbye.")
                    break

                # Special: load a workflow by shared ID directly
                if user_input.lower().startswith("run workflow "):
                    wf_id = user_input.split()[-1]
                    self._run_shared_workflow(wf_id)
                    continue

                # All other inputs route through the intent node
                self._handle_user_turn(user_input)

            except KeyboardInterrupt:
                print("\n[Interrupted]")
                break

    def _handle_user_turn(self, user_input: str) -> None:
        self.history.append({"role": "user", "content": user_input})

        if self.state == SessionState.IDLE:
            self._start_new_workflow(user_input)

        elif self.state == SessionState.PLAN_REVIEW:
            # Intent inference handles all plan editing turns
            intent = self.intent_node.infer(
                user_message=user_input,
                phase="plan_review",
                current_state={"plan": [t.model_dump() for t in self.proposed_plan]},
                conversation_history=self.history
            )
            self._route_plan_intent(intent)

        elif self.state == SessionState.TASK_BUILD:
            # TaskBuilder manages its own intent loop internally
            pass

        elif self.state == SessionState.WORKFLOW_VERIFY:
            intent = self.intent_node.infer(
                user_message=user_input,
                phase="workflow_verify",
                current_state={"workflow": dataclasses.asdict(self.workflow)
                               if self.workflow else {}},
                conversation_history=self.history
            )
            self._route_workflow_intent(intent)

    def _start_new_workflow(self, query: str) -> None:
        print("\n[ORCHESTRATOR] Analyzing your request...")
        parser = IntentParser(self.llm, self.repo)
        self.proposed_plan = parser.parse(query).task_list
        self.state = SessionState.PLAN_REVIEW
        self.display_plan(self.proposed_plan)
        print("\nDoes this plan look right? Tell me in your own words.")

    def display_plan(self, plan: list[TaskStep]) -> None:
        print(f"\n{'─'*60}")
        print("  PROPOSED WORKFLOW PLAN")
        print(f"{'─'*60}")
        for step in plan:
            tag = {"repo": "✓ REPO", "repo_adapted": "~ REPO", "new": "✦ NEW"}
            print(f"  {step.step}. [{tag.get(step.source,'?')}] {step.name}")
            print(f"        {step.description}")
            if step.gap_notes:
                print(f"        NOTE: {step.gap_notes}")
        print(f"{'─'*60}\n")
```

### 8.3 Full Conversation Flow (Happy Path)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WORKFLOW ENGINE  |  Banking Analytics Platform
  Type 'exit' to quit  |  'run workflow <id>' to reuse
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>> I want to extract all working URLs from an uploaded PDF

[ORCHESTRATOR] Analyzing your request...
[Tool Search] searching: "pdf upload"
[Tool Search] searching: "text extract pdf"
[Tool Search] searching: "url extract text"
[Tool Search] searching: "url liveness check"

────────────────────────────────────────────────────────────
  PROPOSED WORKFLOW PLAN
────────────────────────────────────────────────────────────
  1. [✓ REPO] upload_file_v1
        Move/copy a local file into the working directory
  2. [✓ REPO] extract_text_from_pdf_v1
        Extract raw text from PDF using pdfplumber
  3. [✓ REPO] extract_urls_from_text_v1
        Regex + validators URL extraction from raw text
  4. [✓ REPO] check_url_liveness_v1
        Async HEAD requests to URL list, classify live/dead
  5. [✦ NEW] analyze_url_failure_reasons
        Classify why URLs failed: DNS/timeout/4xx/5xx/SSL
────────────────────────────────────────────────────────────

Does this plan look right? Tell me in your own words.
>> looks good but add a dedup step after step 3 and also skip the failure analysis

[SYSTEM] Understood: Add deduplication after URL extraction, and remove the
         failure analysis step entirely.

────────────────────────────────────────────────────────────
  PROPOSED WORKFLOW PLAN
────────────────────────────────────────────────────────────
  1. [✓ REPO] upload_file_v1
  2. [✓ REPO] extract_text_from_pdf_v1
  3. [✓ REPO] extract_urls_from_text_v1
  4. [✓ REPO] deduplicate_list_v1
        Remove duplicates from a list, preserve order
  5. [✓ REPO] check_url_liveness_v1
────────────────────────────────────────────────────────────

Does this plan look right? Tell me in your own words.
>> yeah that's perfect

[PLAN APPROVED]

[GAP DETECTION] All tasks found in repo. No new tasks to build.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW EXECUTOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[GRAPH] Wiring 5 nodes...
[GRAPH] Schema chain validated ✓

Please provide the path to your PDF:
>> /home/user/reports/annual_report_2024.pdf

  [upload_file_v1] starting
  [upload_file_v1] ✓  outputs: ['normalized_path', 'file_size_bytes']
  [extract_text_from_pdf_v1] starting
  [extract_text_from_pdf_v1] ✓  outputs: ['raw_text', 'page_count']
  [extract_urls_from_text_v1] starting
  [extract_urls_from_text_v1] ✓  outputs: ['urls']
  [deduplicate_list_v1] starting
  [deduplicate_list_v1] ✓  outputs: ['unique_items', 'removed_count']
  [check_url_liveness_v1] starting
  [check_url_liveness_v1] ✓  outputs: ['live_urls', 'failed_urls', 'error_map']

────────────────────────────────────────────────────────────
  WORKFLOW OUTPUT
────────────────────────────────────────────────────────────
  Pages processed:  47
  URLs found:       23  (→ 19 unique after dedup)
  Live URLs:        14
  Failed URLs:       5

  Live URLs:
    https://www.fsb.org/publications
    https://www.bis.org/bcbs/publ
    ... (12 more)

  Failed URLs:
    http://expired-domain.com      → DNS_FAILURE
    https://old-report-link.com    → HTTP_404
    ... (3 more)
────────────────────────────────────────────────────────────

Is the workflow output correct? Tell me what you think.
>> yes great work, save this

[REGISTRY] Workflow saved.
  Share ID:  wf_3a9f12bc
  Others can run this with:  >> run workflow wf_3a9f12bc
```

---

## Phase 9: Pre-Seeded Atomic Task Library

All 30+ tasks are bundled under `seeds/atomic_tasks/` and loaded on first boot. Each has a verified `script.py`, `metadata.json`, and `usage_examples`.

### Category 1 — File I/O & Document Processing

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `upload_file_v1` | Move/copy local file to working directory, return normalized path | `file_path` | `normalized_path`, `file_size_bytes` |
| `extract_text_from_pdf_v1` | Full text extraction using pdfplumber, page by page | `file_path` | `raw_text`, `page_count` |
| `extract_tables_from_pdf_v1` | Table extraction using camelot (lattice or stream), returns list of records | `file_path`, `flavor` | `tables_json` |
| `extract_text_from_image_v1` | OCR via pytesseract on PNG/JPG input | `file_path` | `raw_text`, `confidence` |
| `read_excel_sheet_v1` | Read one named sheet from xlsx into records | `file_path`, `sheet_name` | `records`, `columns` |
| `read_csv_v1` | Read CSV with delimiter and type inference into records | `file_path`, `delimiter` | `records`, `columns`, `row_count` |
| `save_to_json_v1` | Write any dict or list to a local JSON file | `data`, `output_path` | `output_path`, `bytes_written` |
| `save_to_csv_v1` | Write list of records to CSV file | `records`, `output_path` | `output_path` |

### Category 2 — Text & NLP Processing

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `extract_urls_from_text_v1` | Regex + validators.url() to pull all URLs from text | `raw_text` | `urls` |
| `extract_emails_from_text_v1` | Regex extraction of all email addresses | `raw_text` | `emails` |
| `extract_dates_from_text_v1` | spaCy date entity extraction, normalised to ISO strings | `raw_text` | `dates` |
| `extract_monetary_values_v1` | Regex extraction of amounts with currency codes | `raw_text` | `monetary_values` (list of `{amount, currency}`) |
| `summarize_text_v1` | LLM-based summarization via Bedrock Claude, max_words controlled | `raw_text`, `max_words` | `summary` |
| `detect_language_v1` | langdetect language identification | `raw_text` | `language_code`, `confidence` |
| `chunk_text_v1` | Split large text into overlapping chunks for downstream processing | `raw_text`, `chunk_size`, `overlap` | `chunks` |
| `classify_document_type_v1` | LLM classifies document: invoice/contract/report/statement/regulatory | `raw_text` | `document_type`, `confidence` |

### Category 3 — Data Transformation & Validation

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `deduplicate_list_v1` | Remove duplicates preserving original order | `items` | `unique_items`, `removed_count` |
| `filter_list_by_pattern_v1` | Regex include/exclude filter on list of strings | `items`, `pattern`, `mode` | `filtered_items` |
| `flatten_nested_dict_v1` | Flatten nested dict to dot-notation keys | `nested_dict` | `flat_dict` |
| `validate_dataframe_schema_v1` | Column presence, type, null-rate checks via great_expectations | `records`, `expected_schema` | `is_valid`, `validation_report` |
| `join_two_datasets_v1` | Inner or left join two lists of records on a shared key | `left_records`, `right_records`, `join_key`, `join_type` | `joined_records` |
| `sort_records_v1` | Sort list of dicts by one or more fields | `records`, `sort_keys`, `ascending` | `sorted_records` |
| `aggregate_records_v1` | Group-by + aggregate: sum/mean/count/max/min | `records`, `group_by`, `agg_field`, `agg_func` | `aggregated_records` |
| `compare_two_datasets_v1` | Surface adds/removes/changes between two datasets by key | `dataset_a`, `dataset_b`, `key_field` | `added`, `removed`, `changed` |

### Category 4 — Web & Network

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `check_url_liveness_v1` | Async HEAD requests to URL list, classify live/dead with timeout | `urls`, `timeout_sec` | `live_urls`, `failed_urls`, `error_map` |
| `classify_url_failure_v1` | Classify failed URLs: DNS/timeout/4xx/5xx/SSL/unknown | `failed_urls`, `error_map` | `failure_report` ({url: reason}) |
| `fetch_webpage_text_v1` | HTTP GET + BeautifulSoup text extraction from a URL | `url` | `text_content`, `title`, `status_code` |
| `parse_html_table_v1` | Extract all tables from HTML string using pandas | `html_content` | `tables_json` |

### Category 5 — Financial & Banking Analytics

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `parse_swift_message_v1` | Parse MT103/MT202 SWIFT message fields into structured dict | `swift_raw_text` | `parsed_fields` |
| `calculate_portfolio_metrics_v1` | Return, volatility, Sharpe ratio from a price series | `price_series`, `risk_free_rate` | `returns`, `volatility`, `sharpe_ratio` |
| `detect_anomalies_in_series_v1` | IQR or Z-score anomaly detection on numeric list | `values`, `method`, `threshold` | `anomalies` (list of {index, value, score}) |
| `compute_summary_statistics_v1` | Mean, median, std, min, max, percentiles | `values` | `stats` dict |
| `classify_transaction_v1` | LLM classifies transaction description into category | `description`, `amount`, `categories` | `category`, `confidence` |
| `extract_invoice_fields_v1` | AWS Textract + LLM: vendor, date, amount, line items from invoice PDF | `file_path` | `vendor`, `date`, `total_amount`, `line_items` |

### Category 6 — Reporting & Output

| task_id | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `render_html_report_v1` | Jinja2 template → HTML report saved locally | `template_path`, `context_data` | `output_path` |
| `format_as_markdown_table_v1` | Convert list of records to Markdown table string | `records` | `markdown_table` |
| `return_output_v1` | Terminal node: pretty-print final result to chat, optionally save to file | `result`, `label` | prints to stdout |
| `log_error_v1` | Append structured error entry to a local error log file | `error_message`, `context` | `log_path` |

---

## Phase 10: How the Three Advanced Tool Use Features Map to Each Phase

| System Phase | Feature Used | Why | Token Impact |
|---|---|---|---|
| **Orchestrator** (propose task list) | **Tool Search Tool** + Tool Use Examples | Only loads task definitions actually needed from 100+ task library | ~3K tokens vs ~20K+ if all loaded upfront (85% reduction) |
| **Task Builder** (script generation) | Standard converse with structured output | Small bounded tool set (~10 tools); no discovery needed | Minimal |
| **Executor** (workflow run) | **Programmatic Tool Calling** + Tool Use Examples | Large intermediate data (URLs, DataFrames) processed in code sandbox; only final result hits Claude's context | ~37% reduction on complex runs |
| **Intent Inference** (every boundary) | `invoke_structured` with schema-forced output | Small, deterministic classification call | Minimal |
| **Plan Negotiator** (edit plan) | Standard converse with history | Conversational edit, no external tools | Managed by history truncation |
| **Workflow Verification** (confirm graph) | Intent inference node | Free-form confirmation/modification | Minimal |

---

## Phase 11: Key Design Decisions Summary

| Concern | Decision | Rationale |
|---|---|---|
| Storage | Local filesystem + Redis VSS | No S3/cloud dependency to start; Redis VSS for fast semantic search |
| Task matching | Titan embeddings + Redis VSS HNSW | Semantic match beats keyword; already in stack |
| Orchestration | RAG candidates via Tool Search → Claude Sonnet structured JSON | Tool Search keeps context lean; LLM understands schema compatibility |
| User interaction | IntentInferenceNode at every boundary | Free-form NL throughout; no rigid command vocabulary |
| New task generation | Claude Sonnet with declared tool registry + Tool Use Examples | LLM knows what's available; generates importable-only code |
| Execution isolation | subprocess + ulimit resource caps | Simple, no Lambda cold starts; sufficient for verified scripts |
| Graph building | Dynamic node wiring, no codegen | Verified scripts are already safe; wiring is declarative |
| Context efficiency | PTC for large-data workflows | Intermediate results stay in code sandbox, not Claude's context |
| Schema validation | At `graph.compile()` time | Fail fast before any data flows |
| Workflow sharing | Content-addressed SHA ID | Same task list → same ID; natural dedup |
| Tool Use Examples | Stored on AtomicTask, generated post-verification | Teach LLM correct invocation patterns not expressible in JSON schema |

---

## Phase 12: Implementation Order

**Week 1 — Core infrastructure**
- Config, local directory setup, Redis VSS, Titan embeddings, Bedrock LLM wrapper
- AtomicTask schema, LocalTaskRepo CRUD, warm-cache-on-start
- Seed all 30+ pre-built tasks from seeds/

**Week 2 — Intent inference + orchestrator**
- IntentInferenceNode with all intent types and phase routing
- Tool Search Tool integration in IntentParser
- Basic REPL loop with state machine

**Week 3 — Plan negotiation + gap detection**
- PlanNegotiator using IntentInferenceNode (NL edits, not rigid commands)
- Gap detector: `source == "new"` identification
- End-to-end test: NL query → approved plan using only repo tasks

**Week 4 — Task Builder**
- Builder loop with sandbox, approach proposal, script generation
- Tool registry prompt, SCRIPT_TEMPLATE standard entry point
- Verifier using IntentInferenceNode (approve/modify/retest/skip)
- usage_examples generation post-verification

**Week 5 — Executor + Registry**
- WorkflowGraph, TaskNode, CompiledWorkflow, schema chain validation
- ProgrammaticWorkflowRunner with PTC for large-data workflows
- WorkflowRegistry with local storage + Redis cache
- run_by_id for shared workflow reuse

**Week 6 — Hardening**
- End-to-end test: 3 banking use cases (invoice extraction, URL audit, transaction classification)
- Error recovery in graph (partial re-run from failed node)
- Task versioning (v1 → v2 on re-verification)
- Session persistence in Redis (resume interrupted sessions)
- Context window management: truncate history beyond 50 turns, keep system + last N turns
