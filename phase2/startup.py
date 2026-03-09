"""Startup and CLI helpers for Phase 2 orchestration.

This module composes the Phase 1 task repository with the Phase 2
clarification-first orchestrator while keeping the original Phase 1 startup
entrypoint unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phase1.repo.local_task_repo import LocalTaskRepo
from phase1.repo.schema import AtomicTask
from phase1.repo.vector_index import ensure_vss_index

from phase2.core import BedrockClaudeLLM, Config, TitanEmbedder
from phase2.chat import PlanningFormatter, PlanningREPL
from phase2.orchestrator import IntentParser, PlanNegotiator
from phase2.orchestrator.models import OrchestrationTurn


@dataclass(slots=True)
class Phase2Runtime:
    """Runtime container for the Phase 2 orchestration stack."""

    cfg: Config
    redis_client: Any
    bedrock_client: Any
    embedder: TitanEmbedder
    llm: BedrockClaudeLLM
    repo: LocalTaskRepo
    parser: IntentParser
    negotiator: PlanNegotiator
    repl: PlanningREPL


def ensure_base_dirs(cfg: Config) -> None:
    """Create the local directory structure shared with the repo."""
    for subdir in ("atomic_tasks", "workflows", "embeddings"):
        (cfg.BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)


def create_redis_client(cfg: Config) -> Any:
    """Create a Redis client using the Phase 1 environment conventions."""
    import redis

    if cfg.REDIS_URL:
        return redis.Redis.from_url(cfg.REDIS_URL)
    return redis.Redis(
        host=cfg.REDIS_HOST,
        port=cfg.REDIS_PORT,
        db=cfg.REDIS_DB,
    )


def create_bedrock_client(cfg: Config) -> Any:
    """Create a Bedrock runtime client."""
    import boto3

    return boto3.client("bedrock-runtime", region_name=cfg.AWS_REGION)


def seed_repo_from_phase1_seeds(repo: LocalTaskRepo, seeds_dir: Path | None = None) -> int:
    """Load Phase 1 seed tasks into the shared repo."""
    base_dir = seeds_dir or (
        Path(__file__).resolve().parents[1]
        / "phase1"
        / "seeds"
        / "atomic_tasks"
    )
    if not base_dir.exists():
        return 0

    count = 0
    for task_dir in sorted(base_dir.iterdir()):
        meta_path = task_dir / "metadata.json"
        script_path = task_dir / "script.py"
        if not (meta_path.exists() and script_path.exists()):
            continue
        task = AtomicTask(**json.loads(meta_path.read_text()))
        repo.upsert_task(task, script_path.read_text())
        count += 1
    return count


def bootstrap_runtime(
    cfg: Config | None = None,
    *,
    redis_client: Any | None = None,
    bedrock_client: Any | None = None,
    repo: LocalTaskRepo | None = None,
) -> Phase2Runtime:
    """Build a Phase 2 runtime with the shared repo and orchestrator."""
    cfg = cfg or Config()
    if repo is None:
        ensure_base_dirs(cfg)

    redis_client = redis_client or create_redis_client(cfg)
    bedrock_client = bedrock_client or create_bedrock_client(cfg)
    embedder = TitanEmbedder(bedrock_client, cfg)

    if repo is None:
        ensure_vss_index(redis_client, embedding_dim=cfg.EMBEDDING_DIM)
        repo = LocalTaskRepo(redis_client, embedder, cfg)
        repo.warm_cache_from_local()
        if redis_client.scard("task:index") == 0:
            seed_repo_from_phase1_seeds(repo)

    llm = BedrockClaudeLLM(bedrock_client, cfg)
    parser = IntentParser(repo, cfg=cfg, llm=llm)
    negotiator = PlanNegotiator(parser)
    repl = PlanningREPL(negotiator, formatter=PlanningFormatter())
    return Phase2Runtime(
        cfg=cfg,
        redis_client=redis_client,
        bedrock_client=bedrock_client,
        embedder=embedder,
        llm=llm,
        repo=repo,
        parser=parser,
        negotiator=negotiator,
        repl=repl,
    )


def parse_answer_pairs(raw_pairs: list[str]) -> dict[str, str]:
    """Parse repeated ``key=value`` CLI arguments into a dict."""
    answers: dict[str, str] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            raise ValueError(
                f"Invalid answer '{pair}'. Expected format question_id=value."
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid answer '{pair}'. Question id is empty.")
        answers[key] = value
    return answers


def run_orchestration(
    request: str,
    *,
    runtime: Phase2Runtime,
    clarification_answers: dict[str, str] | None = None,
) -> OrchestrationTurn:
    """Run one orchestration turn against the prepared runtime."""
    if clarification_answers:
        return runtime.negotiator.answer_clarifications(
            request,
            clarification_answers,
        )
    return runtime.negotiator.start(request)


def render_turn(turn: OrchestrationTurn) -> str:
    """Render an orchestration turn as pretty JSON."""
    return turn.model_dump_json(indent=2)


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Phase 2 orchestration CLI")
    parser.add_argument(
        "--request",
        required=True,
        help="Natural-language workflow request to orchestrate.",
    )
    parser.add_argument(
        "--answer",
        action="append",
        default=[],
        metavar="QUESTION_ID=VALUE",
        help="Answer a clarification question.",
    )
    parser.add_argument(
        "--print-request-payload",
        action="store_true",
        help="Print the prepared Bedrock InvokeModel request payload.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of entering the interactive planning UX.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for Phase 2 orchestration."""
    args = build_arg_parser().parse_args(argv)
    cfg = Config()
    runtime = bootstrap_runtime(cfg)

    if args.print_request_payload:
        payload = runtime.parser.prepare_llm_request(args.request)
        print(json.dumps(payload, indent=2))
        return 0

    answers = parse_answer_pairs(args.answer)
    if not args.json and not answers and sys.stdin.isatty():
        runtime.repl.run(args.request)
        return 0

    turn = run_orchestration(
        args.request,
        runtime=runtime,
        clarification_answers=answers or None,
    )
    if args.json:
        print(render_turn(turn))
    else:
        print(runtime.repl.formatter.format_turn(turn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
