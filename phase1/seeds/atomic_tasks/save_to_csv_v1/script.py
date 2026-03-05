# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       save_to_csv_v1
# input_schema:  {"records": "list[dict]", "output_path": "str"}
# output_schema: {"output_path": "str"}

import json
import sys
from pathlib import Path

import pandas as pd


def execute(inputs: dict) -> dict:
    """Write list of records to a CSV file."""
    records = inputs["records"]
    output_path = inputs["output_path"]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)

    return {"output_path": output_path}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
