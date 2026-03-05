# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       read_excel_sheet_v1
# input_schema:  {"file_path": "str", "sheet_name": "str"}
# output_schema: {"records": "list[dict]", "columns": "list[str]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Read one named sheet from an xlsx file into records."""
    file_path = inputs["file_path"]
    sheet_name = inputs.get("sheet_name", "Sheet1")

    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    # Convert NaN to None for JSON serialisation
    df = df.where(df.notna(), None)

    return {
        "records": df.to_dict(orient="records"),
        "columns": list(df.columns),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
