# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       filter_list_by_pattern_v1
# input_schema:  {"items": "list[str]", "pattern": "str", "mode": "str"}
# output_schema: {"filtered_items": "list[str]"}

import json
import re
import sys


def execute(inputs: dict) -> dict:
    """Filter strings by regex pattern in include or exclude mode."""
    items = inputs["items"]
    pattern = re.compile(inputs["pattern"])
    mode = inputs.get("mode", "include").lower()

    if mode == "include":
        filtered = [item for item in items if pattern.search(item)]
    elif mode == "exclude":
        filtered = [item for item in items if not pattern.search(item)]
    else:
        raise ValueError(f"mode must be 'include' or 'exclude', got '{mode}'")

    return {"filtered_items": filtered}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
