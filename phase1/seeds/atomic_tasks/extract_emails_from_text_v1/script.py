# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_emails_from_text_v1
# input_schema:  {"raw_text": "str"}
# output_schema: {"emails": "list[str]"}

import json
import re
import sys


def execute(inputs: dict) -> dict:
    """Extract email addresses from raw text via regex."""
    raw_text = inputs["raw_text"]

    email_pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )

    emails = list(set(email_pattern.findall(raw_text)))
    emails.sort()

    return {"emails": emails}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
