# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       log_error_v1
# input_schema:  {"error_message": "str", "context": "dict"}
# output_schema: {"log_path": "str"}

import json
import sys
from datetime import datetime
from pathlib import Path


def execute(inputs: dict) -> dict:
    """Append a structured error to the local error log."""
    error_message = inputs["error_message"]
    context = inputs.get("context", {})

    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "error_log.jsonl"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "error_message": error_message,
        "context": context,
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {"log_path": str(log_path)}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
