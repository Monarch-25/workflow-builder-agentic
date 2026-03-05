# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       compare_two_datasets_v1
# input_schema:  {"dataset_a": "list[dict]", "dataset_b": "list[dict]", "key_field": "str"}
# output_schema: {"added": "list[dict]", "removed": "list[dict]", "changed": "list[dict]"}

import json
import sys


def execute(inputs: dict) -> dict:
    """Compare two datasets by key field — find added/removed/changed."""
    dataset_a = inputs["dataset_a"]
    dataset_b = inputs["dataset_b"]
    key_field = inputs["key_field"]

    map_a = {r[key_field]: r for r in dataset_a}
    map_b = {r[key_field]: r for r in dataset_b}

    keys_a = set(map_a.keys())
    keys_b = set(map_b.keys())

    added = [map_b[k] for k in sorted(keys_b - keys_a, key=str)]
    removed = [map_a[k] for k in sorted(keys_a - keys_b, key=str)]

    changed: list[dict] = []
    for k in sorted(keys_a & keys_b, key=str):
        if map_a[k] != map_b[k]:
            changed.append({"key": k, "before": map_a[k], "after": map_b[k]})

    return {"added": added, "removed": removed, "changed": changed}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
