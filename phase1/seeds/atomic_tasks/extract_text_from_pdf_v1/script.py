# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_text_from_pdf_v1
# input_schema:  {"file_path": "str"}
# output_schema: {"raw_text": "str", "page_count": "int"}

import json
import sys

import pdfplumber


def execute(inputs: dict) -> dict:
    """Extract text from every page of a PDF using pdfplumber."""
    file_path = inputs["file_path"]
    pages_text: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    return {
        "raw_text": "\n\n".join(pages_text),
        "page_count": len(pages_text),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
