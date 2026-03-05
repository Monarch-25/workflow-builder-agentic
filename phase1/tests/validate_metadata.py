"""
Validate all seed task metadata.json files against the AtomicTask schema.

This test requires NO external services — it runs purely locally.

Usage:
    cd phase1/
    python tests/validate_metadata.py
"""

import json
import sys
from pathlib import Path

# Add parent to path so we can import repo.schema
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "repo.schema",
    Path(__file__).resolve().parent.parent / "repo" / "schema.py",
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
AtomicTask = _module.AtomicTask


def main() -> None:
    seeds_dir = Path(__file__).resolve().parent.parent / "seeds" / "atomic_tasks"
    if not seeds_dir.exists():
        print(f"ERROR: seeds directory not found at {seeds_dir}")
        sys.exit(1)

    errors: list[str] = []
    count = 0

    for task_dir in sorted(seeds_dir.iterdir()):
        meta_path = task_dir / "metadata.json"
        script_path = task_dir / "script.py"

        if not meta_path.exists():
            errors.append(f"  {task_dir.name}: missing metadata.json")
            continue
        if not script_path.exists():
            errors.append(f"  {task_dir.name}: missing script.py")
            continue

        try:
            raw = json.loads(meta_path.read_text())
            task = AtomicTask(**raw)

            # Validate task_id matches directory name
            if task.task_id != task_dir.name:
                errors.append(
                    f"  {task_dir.name}: task_id '{task.task_id}' "
                    f"does not match directory name"
                )

            # script_path must be relative and resolve within the task folder
            script_rel_path = Path(task.script_path)
            if script_rel_path.is_absolute():
                errors.append(
                    f"  {task_dir.name}: script_path must be relative, got absolute path"
                )
            else:
                resolved_script = (task_dir / script_rel_path).resolve()
                try:
                    resolved_script.relative_to(task_dir.resolve())
                except ValueError:
                    errors.append(
                        f"  {task_dir.name}: script_path escapes task directory"
                    )
                if not resolved_script.exists():
                    errors.append(
                        f"  {task_dir.name}: script_path '{task.script_path}' not found"
                    )

            # Check script has execute function
            script_content = script_path.read_text()
            if "def execute(" not in script_content:
                errors.append(
                    f"  {task_dir.name}: script.py missing execute() function"
                )

            count += 1
        except json.JSONDecodeError as exc:
            errors.append(f"  {task_dir.name}: invalid JSON — {exc}")
        except Exception as exc:
            errors.append(f"  {task_dir.name}: validation failed — {exc}")

    # Report
    print(f"\nValidated {count} seed tasks from {seeds_dir.name}/")
    if errors:
        print(f"\n{len(errors)} error(s) found:")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("All metadata files are valid. ✓")
        sys.exit(0)


if __name__ == "__main__":
    main()
