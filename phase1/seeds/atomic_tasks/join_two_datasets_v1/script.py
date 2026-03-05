# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       join_two_datasets_v1
# input_schema:  {"left_records": "list[dict]", "right_records": "list[dict]", "join_key": "str", "join_type": "str"}
# output_schema: {"joined_records": "list[dict]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Join two lists of records on a shared key."""
    left = pd.DataFrame(inputs["left_records"])
    right = pd.DataFrame(inputs["right_records"])
    join_key = inputs["join_key"]
    join_type = inputs.get("join_type", "inner")

    merged = pd.merge(left, right, on=join_key, how=join_type)
    merged = merged.where(merged.notna(), None)

    return {"joined_records": merged.to_dict(orient="records")}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
