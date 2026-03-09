"""Local-only helpers for Phase 2 tests."""

from __future__ import annotations

import json
from pathlib import Path

from phase1.repo.schema import AtomicTask


class InMemoryTaskRepo:
    """Simple task repo with keyword-overlap search for local tests."""

    def __init__(self, tasks: list[AtomicTask]) -> None:
        self._tasks = {task.task_id: task for task in tasks}

    def list_all_tasks(self) -> list[str]:
        return sorted(self._tasks)

    def get_task(self, task_id: str) -> AtomicTask:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise FileNotFoundError(task_id) from exc

    def search_similar_tasks(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[AtomicTask]:
        terms = set(query.lower().split())
        scored = []
        for task in self._tasks.values():
            haystack = " ".join(
                [
                    task.task_id.replace("_", " "),
                    task.name.lower(),
                    task.description.lower(),
                    " ".join(task.tags).lower(),
                ]
            )
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, task))
        scored.sort(key=lambda item: (-item[0], item[1].task_id))
        limit = top_k if top_k is not None else len(scored)
        return [task for _, task in scored[:limit]]


def load_seed_tasks(*task_ids: str) -> list[AtomicTask]:
    """Load selected Phase 1 seed tasks from local metadata files."""
    base = (
        Path(__file__).resolve().parents[2]
        / "phase1"
        / "seeds"
        / "atomic_tasks"
    )
    tasks: list[AtomicTask] = []
    for task_id in task_ids:
        metadata_path = base / task_id / "metadata.json"
        payload = json.loads(metadata_path.read_text())
        tasks.append(AtomicTask(**payload))
    return tasks

