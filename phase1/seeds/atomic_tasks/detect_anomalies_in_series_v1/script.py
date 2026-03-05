# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       detect_anomalies_in_series_v1
# input_schema:  {"values": "list[float]", "method": "str", "threshold": "float"}
# output_schema: {"anomalies": "list[dict]"}

import json
import sys

import numpy as np


def execute(inputs: dict) -> dict:
    """Detect anomalies using IQR or Z-score method."""
    values = np.array(inputs["values"], dtype=np.float64)
    method = inputs.get("method", "zscore").lower()
    threshold = inputs.get("threshold", 2.0)

    anomalies: list[dict] = []

    if method == "zscore":
        mean = np.mean(values)
        std = np.std(values, ddof=1)
        if std == 0:
            return {"anomalies": []}
        z_scores = np.abs((values - mean) / std)
        for i, (val, score) in enumerate(zip(values, z_scores)):
            if score > threshold:
                anomalies.append({"index": i, "value": float(val), "score": float(score)})

    elif method == "iqr":
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr
        for i, val in enumerate(values):
            if val < lower or val > upper:
                score = abs(val - np.median(values)) / (iqr if iqr > 0 else 1.0)
                anomalies.append({"index": i, "value": float(val), "score": float(score)})
    else:
        raise ValueError(f"method must be 'zscore' or 'iqr', got '{method}'")

    return {"anomalies": anomalies}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
