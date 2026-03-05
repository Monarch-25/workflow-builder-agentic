# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       save_to_json_v1
# input_schema:  {"data": "any", "output_path": "str"}
# output_schema: {"output_path": "str", "bytes_written": "int"}

import json
import sys
from pathlib import Path


def execute(inputs: dict) -> dict:
    """Write data to a JSON file."""
    data = inputs["data"]
    output_path = inputs["output_path"]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, indent=2, default=str)
    Path(output_path).write_text(content)

    return {
        "output_path": output_path,
        "bytes_written": len(content.encode("utf-8")),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
