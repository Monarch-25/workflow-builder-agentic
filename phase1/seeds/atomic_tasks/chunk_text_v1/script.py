# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       chunk_text_v1
# input_schema:  {"raw_text": "str", "chunk_size": "int", "overlap": "int"}
# output_schema: {"chunks": "list[str]"}

import json
import sys


def execute(inputs: dict) -> dict:
    """Split text into overlapping chunks."""
    raw_text = inputs["raw_text"]
    chunk_size = inputs.get("chunk_size", 1000)
    overlap = inputs.get("overlap", 100)

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    text_len = len(raw_text)

    while start < text_len:
        end = start + chunk_size
        chunks.append(raw_text[start:end])
        start += chunk_size - overlap

    return {"chunks": chunks}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
