# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_urls_from_text_v1
# input_schema:  {"raw_text": "str"}
# output_schema: {"urls": "list[str]"}

import json
import re
import sys

import validators


def execute(inputs: dict) -> dict:
    """Extract all valid URLs from raw text using regex + validators."""
    raw_text = inputs["raw_text"]

    # Broad regex to capture candidate URLs
    url_pattern = re.compile(
        r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE
    )

    candidates = url_pattern.findall(raw_text)

    # Strip trailing punctuation that was captured
    cleaned: list[str] = []
    for url in candidates:
        url = url.rstrip(".,;:!?)")
        if validators.url(url):
            cleaned.append(url)

    return {"urls": cleaned}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
