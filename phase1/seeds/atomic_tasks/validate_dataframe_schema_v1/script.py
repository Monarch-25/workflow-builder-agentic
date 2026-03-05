# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       validate_dataframe_schema_v1
# input_schema:  {"records": "list[dict]", "expected_schema": "dict"}
# output_schema: {"is_valid": "bool", "validation_report": "list[dict]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Validate records against an expected schema."""
    records = inputs["records"]
    schema = inputs["expected_schema"]

    df = pd.DataFrame(records)
    report: list[dict] = []
    all_valid = True

    # Column presence check
    expected_cols = schema.get("columns", [])
    for col in expected_cols:
        if col not in df.columns:
            report.append({"check": "column_presence", "column": col, "passed": False, "detail": "missing"})
            all_valid = False
        else:
            report.append({"check": "column_presence", "column": col, "passed": True, "detail": "present"})

    # Null rate check
    max_null_rate = schema.get("max_null_rate", 1.0)
    for col in df.columns:
        if col in expected_cols:
            null_rate = df[col].isnull().mean()
            passed = null_rate <= max_null_rate
            if not passed:
                all_valid = False
            report.append({
                "check": "null_rate",
                "column": col,
                "passed": passed,
                "detail": f"null_rate={null_rate:.4f} (max={max_null_rate})",
            })

    return {"is_valid": all_valid, "validation_report": report}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
