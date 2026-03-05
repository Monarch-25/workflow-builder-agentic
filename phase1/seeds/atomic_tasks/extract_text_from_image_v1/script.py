# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_text_from_image_v1
# input_schema:  {"file_path": "str"}
# output_schema: {"raw_text": "str", "confidence": "float"}

import json
import sys

import pytesseract
from PIL import Image


def execute(inputs: dict) -> dict:
    """OCR on a PNG/JPG image via pytesseract."""
    file_path = inputs["file_path"]
    image = Image.open(file_path)

    # Get detailed data for confidence estimation
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidences = [
        int(c) for c in data["conf"] if str(c).strip() != "-1"
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    raw_text = pytesseract.image_to_string(image)

    return {
        "raw_text": raw_text.strip(),
        "confidence": round(avg_confidence / 100.0, 4),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
