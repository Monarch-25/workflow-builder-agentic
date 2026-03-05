# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       parse_html_table_v1
# input_schema:  {"html_content": "str"}
# output_schema: {"tables_json": "list[list[dict]]"}

import json
import sys

import pandas as pd


def execute(inputs: dict) -> dict:
    """Extract all HTML tables as lists of records."""
    html = inputs["html_content"]

    try:
        dfs = pd.read_html(html)
    except ValueError:
        return {"tables_json": []}

    tables_json: list[list[dict]] = []
    for df in dfs:
        df = df.where(df.notna(), None)
        tables_json.append(df.to_dict(orient="records"))

    return {"tables_json": tables_json}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f, default=str)
