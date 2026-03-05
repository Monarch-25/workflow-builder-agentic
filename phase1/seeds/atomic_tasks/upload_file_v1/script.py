# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       upload_file_v1
# input_schema:  {"file_path": "str"}
# output_schema: {"normalized_path": "str", "file_size_bytes": "int"}

import json
import os
import shutil
import sys
from pathlib import Path


def execute(inputs: dict) -> dict:
    """Copy or move a file into the working directory, return normalised path."""
    file_path = Path(inputs["file_path"]).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    # Working directory: current working dir / input_files
    work_dir = Path.cwd() / "input_files"
    work_dir.mkdir(parents=True, exist_ok=True)

    dest = work_dir / file_path.name

    # Copy (preserving metadata) rather than move to keep the original
    shutil.copy2(str(file_path), str(dest))

    return {
        "normalized_path": str(dest.resolve()),
        "file_size_bytes": dest.stat().st_size,
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
