# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       format_as_markdown_table_v1
# input_schema:  {"records": "list[dict]"}
# output_schema: {"markdown_table": "str"}

import json
import sys


def execute(inputs: dict) -> dict:
    """Convert records to a Markdown table."""
    records = inputs["records"]
    if not records:
        return {"markdown_table": "_(no data)_"}

    columns = list(records[0].keys())

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"

    # Rows
    rows: list[str] = []
    for record in records:
        values = [str(record.get(col, "")) for col in columns]
        rows.append("| " + " | ".join(values) + " |")

    table = "\n".join([header, separator] + rows)
    return {"markdown_table": table}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
