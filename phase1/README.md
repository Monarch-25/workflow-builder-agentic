# Workflow Engine — Phase 1: Core Infrastructure

## Overview

Phase 1 provides the foundational layer of the Workflow Engine:

- **Core module** — Config, BedrockClaudeLLM wrapper, TitanEmbedder
- **Repo module** — AtomicTask schema, LocalTaskRepo (filesystem + Redis), Redis VSS index
- **38 pre-built seed tasks** — File I/O, NLP, Data, Web, Finance, Reporting
- **Startup** — Bootstraps directories, Redis index, and seeds the task repo

## Prerequisites

- **Python** 3.11+
- **Redis** 7+ with the [RediSearch](https://redis.io/docs/interact/search-and-query/) module enabled
- **AWS credentials** configured — either via environment variables or `~/.aws/credentials`
- **Tesseract OCR** installed (for `extract_text_from_image_v1`) — `brew install tesseract`

## Setup

### 1. Install dependencies

```bash
cd workflow_builder/phase1/
pip install -r requirements.txt
```

### 2. Start Redis locally

```bash
# Using Docker (recommended — includes RediSearch module):
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest

# Or via brew (macOS):
brew install redis
redis-server
```

### 3. Create `.env` file

Create a `.env` file in the `phase1/` directory:

```env
# AWS
AWS_REGION=us-east-1
BEDROCK_CLAUDE_MODEL=anthropic.claude-sonnet-4-5
BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0
LOG_LLM_REQUESTS=false   # set true to log Bedrock request payloads

# Redis (pick one style)
# REDIS_URL=redis://localhost:6380/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Local storage
# BASE_DIR=~/.workflow_engine    # default
```

### 4. Run startup

```bash
python startup.py
```

Expected output:
```
[STARTUP] Redis VSS index ready.
[STARTUP] Warmed cache — 0 tasks in index.
[STARTUP] Seeded 38 atomic tasks from seeds/.
[STARTUP] Workflow Engine ready.
  Base directory : /home/user/.workflow_engine
  Redis          : localhost:6379/0
  Bedrock model  : anthropic.claude-sonnet-4-5
  Tasks indexed  : 38
```

## Project Structure

```
phase1/
├── core/
│   ├── __init__.py
│   ├── config.py           # Pydantic settings from .env
│   ├── llm.py              # BedrockClaudeLLM wrapper
│   └── embeddings.py       # TitanEmbedder wrapper
├── repo/
│   ├── __init__.py
│   ├── schema.py           # AtomicTask Pydantic model
│   ├── local_task_repo.py  # CRUD + VSS search + warm cache
│   └── vector_index.py     # Redis VSS index setup
├── seeds/
│   ├── __init__.py
│   ├── seed_loader.py      # Loads seeds into repo
│   └── atomic_tasks/       # 38 task directories
│       ├── upload_file_v1/
│       │   ├── script.py
│       │   └── metadata.json
│       └── ...
├── tests/
│   └── validate_metadata.py
├── startup.py
├── requirements.txt
└── README.md
```

## Seed Task Categories

| Category | Count | LLM-based? |
|----------|-------|------------|
| File I/O & Document Processing | 8 | No |
| Text & NLP Processing | 8 | 5 use Bedrock, 3 regex/mechanical |
| Data Transformation & Validation | 8 | No |
| Web & Network | 4 | No |
| Financial & Banking Analytics | 6 | 2 use Bedrock |
| Reporting & Output | 4 | No |

All LLM-based tasks accept a configurable `model_id` parameter and include **Pydantic output validation** to ensure the LLM response matches the expected schema.

## Notes

- Task metadata stores `script_path` as a **relative path** (`script.py`) for cross-machine portability.
- `LocalTaskRepo` supports full CRUD lifecycle (`upsert_task`, `get_task`, `get_script`, `delete_task`) plus semantic search and warm-cache.

## Verification

```bash
# Syntax check all Python files
find . -name "*.py" -exec python3 -m py_compile {} \;

# Validate all metadata.json files against the AtomicTask schema
python tests/validate_metadata.py
```
