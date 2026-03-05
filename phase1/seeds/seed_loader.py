"""
Seed loader — populates the task repo with pre-built atomic tasks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from repo.schema import AtomicTask

if TYPE_CHECKING:
    from core.config import Config
    from repo.local_task_repo import LocalTaskRepo


def seed_atomic_tasks(repo: "LocalTaskRepo", cfg: "Config") -> int:
    """
    Walk ``seeds/atomic_tasks/*/`` and upsert each task into the repo.

    Returns the number of tasks seeded.
    """
    seeds_dir = Path(__file__).resolve().parent / "atomic_tasks"
    if not seeds_dir.exists():
        return 0

    count = 0
    for task_dir in sorted(seeds_dir.iterdir()):
        meta_path = task_dir / "metadata.json"
        script_path = task_dir / "script.py"
        if not (meta_path.exists() and script_path.exists()):
            continue

        meta = json.loads(meta_path.read_text())
        task = AtomicTask(**meta)
        script = script_path.read_text()

        repo.upsert_task(task, script)
        count += 1

    return count
