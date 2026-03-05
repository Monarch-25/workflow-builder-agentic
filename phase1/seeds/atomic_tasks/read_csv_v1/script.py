# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       read_csv_v1
# input_schema:  {"file_path": "str", "delimiter": "str"}
# output_schema: {"records": "list[dict]", "columns": "list[str]", "row_count": "int"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Read a CSV with the given delimiter and return records."""
    file_path = inputs["file_path"]
    delimiter = inputs.get("delimiter", ",")

    df = pd.read_csv(file_path, delimiter=delimiter)
    df = df.where(df.notna(), None)

    return {
        "records": df.to_dict(orient="records"),
        "columns": list(df.columns),
        "row_count": len(df),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
