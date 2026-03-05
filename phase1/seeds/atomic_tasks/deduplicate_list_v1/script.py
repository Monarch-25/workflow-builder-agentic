# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       deduplicate_list_v1
# input_schema:  {"items": "list"}
# output_schema: {"unique_items": "list", "removed_count": "int"}

import json
import sys


def execute(inputs: dict) -> dict:
    """Remove duplicates preserving order of first occurrence."""
    items = inputs["items"]
    seen: set = set()
    unique: list = []
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else item
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "unique_items": unique,
        "removed_count": len(items) - len(unique),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
