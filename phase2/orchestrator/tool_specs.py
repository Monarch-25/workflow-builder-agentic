"""Tool-spec compilation for the interactive orchestrator."""

from __future__ import annotations

import re

from phase1.repo.schema import AtomicTask

TOOL_SEARCH_NAME = "tool_search"
TOOL_SEARCH_TYPE = "tool_search_tool_regex_20251119"
DEFAULT_ANCHOR_TASKS = (
    "upload_file_v1",
    "return_output_v1",
    "log_error_v1",
)


def build_search_aliases(task: AtomicTask) -> list[str]:
    """Derive simple aliases from task ids, names, and tags."""
    pieces = re.split(r"[_\W]+", f"{task.task_id} {task.name}".lower())
    aliases = list(task.tags)
    aliases.extend(piece for piece in pieces if piece and not piece.startswith("v"))
    unique_aliases: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = alias.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_aliases.append(normalized)
    return unique_aliases


def _format_schema(schema: dict) -> str:
    if not schema:
        return "none"
    return ", ".join(f"{name}: {type_hint}" for name, type_hint in schema.items())


def build_tool_description(task: AtomicTask) -> str:
    """Expand tool descriptions so Claude can reason with less hidden context."""
    tags = ", ".join(task.tags) if task.tags else "none"
    aliases = ", ".join(build_search_aliases(task)) or "none"
    return (
        f"{task.description} "
        f"Inputs: {_format_schema(task.input_schema)}. "
        f"Outputs: {_format_schema(task.output_schema)}. "
        f"Tags: {tags}. "
        f"Search aliases: {aliases}."
    )


def build_orchestrator_tools(
    all_tasks: list[AtomicTask],
    anchor_task_ids: tuple[str, ...] = DEFAULT_ANCHOR_TASKS,
) -> list[dict]:
    """Build native Bedrock tool specs with deferred loading for non-anchors."""
    tools: list[dict] = [
        {
            "type": TOOL_SEARCH_TYPE,
            "name": TOOL_SEARCH_NAME,
        }
    ]

    anchors = set(anchor_task_ids)
    for task in sorted(all_tasks, key=lambda item: item.task_id):
        tool_entry = {
            "name": task.task_id,
            "description": build_tool_description(task),
            "input_schema": task.input_schema,
        }
        if task.usage_examples:
            tool_entry["input_examples"] = task.usage_examples[:3]
        if task.task_id not in anchors:
            tool_entry["defer_loading"] = True
        tools.append(tool_entry)
    return tools

