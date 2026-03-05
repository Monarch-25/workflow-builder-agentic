# Phase 1 Fixes (fixes1)

Date: 2026-03-05
Scope: `phase1/` implementation alignment with `Implementation_plan/phase1.md`, `workflow_engine_full_plan.md`, and `rules.md` constraints.

## Summary of Fixes

### 1) Fixed Redis VSS schema mismatch (critical)

Problem:
- Tasks were stored as Redis HASH fields, but index fields were declared as JSON paths (`$.field`), which can break KNN search.

Changes:
- Updated index field declarations to HASH field names (`task_id`, `name`, `description`, `embedding`).
- Added `embedding_dim` argument to `ensure_vss_index(...)` and wired startup to config dimension.
- Added redis-py import compatibility for both:
  - `redis.commands.search.index_definition`
  - `redis.commands.search.indexDefinition`

Files:
- `phase1/repo/vector_index.py`
- `phase1/startup.py`

### 2) Enforced relative `script_path` for portability (as requested)

Problem:
- Seed metadata had empty `script_path` values.
- Schema/documentation expectation previously referenced absolute paths.

Changes:
- Updated `AtomicTask.script_path` to default to `"script.py"`, require non-empty value, and document it as relative/portable.
- Updated `LocalTaskRepo.upsert_task(...)` to persist canonical relative `script_path="script.py"`.
- Updated `LocalTaskRepo.get_script(...)` to:
  - reject absolute paths
  - reject path traversal outside task directory
- Normalized all seed metadata files: `"script_path": "script.py"` (38/38).

Files:
- `phase1/repo/schema.py`
- `phase1/repo/local_task_repo.py`
- `phase1/seeds/atomic_tasks/*/metadata.json` (all seed tasks)

### 3) Added missing CRUD delete operation

Problem:
- Repo had upsert/read/list/search/warm, but no delete method.

Changes:
- Added `delete_task(task_id)` to remove:
  - local task directory
  - `task:meta:{task_id}`
  - `task:vec:{task_id}`
  - `task:index` membership

Files:
- `phase1/repo/local_task_repo.py`

### 4) Added request payload logging for advanced tool-use verification

Problem:
- Acceptance criteria asks that advanced-tool-use header can be verified in logged payload.

Changes:
- Added config flag: `LOG_LLM_REQUESTS` (default `false`).
- Added optional `logger.info(...)` request payload logging in `BedrockClaudeLLM.converse()`.

Files:
- `phase1/core/config.py`
- `phase1/core/llm.py`
- `phase1/README.md` (`.env` example includes `LOG_LLM_REQUESTS`)

### 5) Strengthened local metadata validation

Changes:
- `tests/validate_metadata.py` now checks:
  - `script_path` is relative
  - `script_path` does not escape task directory
  - `script_path` resolves to an existing file

Files:
- `phase1/tests/validate_metadata.py`

### 6) Documentation updates

Changes:
- Added portability note for relative `script_path`.
- Documented full CRUD note including `delete_task`.

Files:
- `phase1/README.md`

## Validation Performed (Local Only)

Environment requested by user:
- `conda` env: `mambaGPT`

Commands run:

1. Syntax compilation (all Python files)
```bash
conda run -n mambaGPT bash -lc "find phase1 -name '*.py' -not -path '*/__pycache__/*' -exec python -m py_compile {} \;"
```
Result: Passed (exit code 0)

2. Seed metadata validation
```bash
conda run -n mambaGPT bash -lc "python phase1/tests/validate_metadata.py"
```
Result: Passed
- `Validated 38 seed tasks from atomic_tasks/`
- `All metadata files are valid. ✓`

## Not Executed (Rules/Sandbox Boundaries)

- No Bedrock calls were executed.
- Redis integration smoke test could not be executed in this harness due sandbox socket restrictions (`localhost:6379` connection denied).

## Key Updated Files

- `phase1/core/config.py`
- `phase1/core/llm.py`
- `phase1/repo/schema.py`
- `phase1/repo/local_task_repo.py`
- `phase1/repo/vector_index.py`
- `phase1/startup.py`
- `phase1/tests/validate_metadata.py`
- `phase1/README.md`
- `phase1/seeds/atomic_tasks/*/metadata.json` (script_path normalized)
