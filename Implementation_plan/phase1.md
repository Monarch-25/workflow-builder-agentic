Story 1
Story Name: Set Up Core Infrastructure — Local Task Repo, Redis VSS, and Bedrock Wrappers
What:

Build the local filesystem-based atomic task repository (~/.workflow_engine/atomic_tasks/) with full CRUD operations including script storage and metadata management
Implement Redis Vector Similarity Search (VSS) index using the HNSW algorithm with Titan embeddings for semantic task lookup, including cold-start warm-up from local files
Create the BedrockClaudeLLM and TitanEmbedder wrappers with support for the advanced tool use beta header (additionalModelRequestFields) required for Tool Search and Programmatic Tool Calling
Seed the repository with the full library of 30+ pre-built verified atomic tasks across all categories (file I/O, NLP, financial, web, reporting) with metadata and usage examples

Why:

This is the foundational layer that every other component in the Workflow Automation Engine MVP depends on — without a working task repo, semantic search, and LLM connectivity, no subsequent stories can be built or tested
Establishing local storage first (rather than S3) unblocks parallel development immediately without cloud configuration overhead
The Redis VSS index is the core of the RAG-based task matching strategy; getting the embedding pipeline and index schema correct early avoids costly rework later
Pre-seeding 30+ verified tasks gives the orchestrator and executor meaningful data to work with from day one, enabling realistic end-to-end testing across all future stories

Acceptance Criteria:

A fellow developer can run python startup.py on a clean machine with only Redis and AWS credentials configured, and all 30+ seed tasks are indexed and retrievable via repo.search_similar_tasks("extract text from pdf") returning relevant results
repo.get_task(task_id) correctly hits Redis cache on the second call (verifiable via Redis MONITOR or TTL inspection) and falls back to local filesystem on a cache miss
BedrockClaudeLLM.converse() called with enable_advanced_tools=True produces a request containing additionalModelRequestFields: {"anthropic_beta": ["advanced-tool-use-2025-11-20"]} (verifiable via a logged request payload)
Running warm_cache_from_local() on a fresh Redis instance repopulates all task vectors and metadata without error, and redis.scard("task:index") equals the number of seed tasks on disk

Artifacts:

core/config.py, core/llm.py, core/embeddings.py
repo/local_task_repo.py, repo/vector_index.py, repo/schema.py
seeds/atomic_tasks/ — 30+ task directories each with script.py and metadata.json
startup.py with seeding and warm-cache logic
A short README.md section documenting local setup, Redis startup, and .env required variables