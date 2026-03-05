# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       sort_records_v1
# input_schema:  {"records": "list[dict]", "sort_keys": "list[str]", "ascending": "bool"}
# output_schema: {"sorted_records": "list[dict]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Sort records by one or more fields."""
    records = inputs["records"]
    sort_keys = inputs["sort_keys"]
    ascending = inputs.get("ascending", True)

    df = pd.DataFrame(records)
    df = df.sort_values(by=sort_keys, ascending=ascending).reset_index(drop=True)
    df = df.where(df.notna(), None)

    return {"sorted_records": df.to_dict(orient="records")}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
