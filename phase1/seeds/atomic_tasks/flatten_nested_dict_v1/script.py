# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       flatten_nested_dict_v1
# input_schema:  {"nested_dict": "dict"}
# output_schema: {"flat_dict": "dict"}

import json
import sys


def _flatten(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items: list[tuple[str, object]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def execute(inputs: dict) -> dict:
    """Flatten nested dict to dot-notation keys."""
    return {"flat_dict": _flatten(inputs["nested_dict"])}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
