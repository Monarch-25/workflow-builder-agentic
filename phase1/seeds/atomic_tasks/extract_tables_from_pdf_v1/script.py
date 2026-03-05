# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_tables_from_pdf_v1
# input_schema:  {"file_path": "str", "flavor": "str"}
# output_schema: {"tables_json": "list[list[dict]]"}

import json
import sys

import camelot


def execute(inputs: dict) -> dict:
    """Extract tables from a PDF using camelot (lattice or stream)."""
    file_path = inputs["file_path"]
    flavor = inputs.get("flavor", "lattice")

    tables = camelot.read_pdf(file_path, flavor=flavor, pages="all")

    tables_json: list[list[dict]] = []
    for table in tables:
        df = table.df
        # Use the first row as header if it looks like one
        if len(df) > 1:
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
        tables_json.append(df.to_dict(orient="records"))

    return {"tables_json": tables_json}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
