# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       return_output_v1
# input_schema:  {"result": "any", "label": "str"}
# output_schema: {}

import json
import sys


def execute(inputs: dict) -> dict:
    """Pretty-print final workflow output to stdout."""
    result = inputs["result"]
    label = inputs.get("label", "Output")

    separator = "─" * 60
    print(f"\n{separator}")
    print(f"  {label}")
    print(f"{separator}")

    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, list) and len(value) > 5:
                print(f"  {key}: [{len(value)} items]")
                for item in value[:5]:
                    print(f"    - {item}")
                print(f"    ... ({len(value) - 5} more)")
            else:
                print(f"  {key}: {value}")
    else:
        print(f"  {result}")

    print(f"{separator}\n")

    return {}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
