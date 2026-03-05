# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       aggregate_records_v1
# input_schema:  {"records": "list[dict]", "group_by": "str", "agg_field": "str", "agg_func": "str"}
# output_schema: {"aggregated_records": "list[dict]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Group-by + aggregate on records."""
    df = pd.DataFrame(inputs["records"])
    group_by = inputs["group_by"]
    agg_field = inputs["agg_field"]
    agg_func = inputs.get("agg_func", "sum")

    valid_funcs = {"sum", "mean", "count", "max", "min"}
    if agg_func not in valid_funcs:
        raise ValueError(f"agg_func must be one of {valid_funcs}, got '{agg_func}'")

    result = df.groupby(group_by)[agg_field].agg(agg_func).reset_index()
    result.columns = [group_by, f"{agg_field}_{agg_func}"]

    return {"aggregated_records": result.to_dict(orient="records")}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
