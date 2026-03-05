# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       compute_summary_statistics_v1
# input_schema:  {"values": "list[float]"}
# output_schema: {"stats": "dict"}

import json
import sys

import numpy as np


def execute(inputs: dict) -> dict:
    """Compute descriptive statistics for a list of values."""
    values = np.array(inputs["values"], dtype=np.float64)

    stats = {
        "count": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "p25": float(np.percentile(values, 25)),
        "p50": float(np.percentile(values, 50)),
        "p75": float(np.percentile(values, 75)),
    }

    return {"stats": stats}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
