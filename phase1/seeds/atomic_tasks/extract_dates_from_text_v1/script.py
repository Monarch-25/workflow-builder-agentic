# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_dates_from_text_v1
# input_schema:  {"raw_text": "str", "model_id": "str"}
# output_schema: {"dates": "list[str]"}

import json
import os
import sys
from typing import Any

import boto3
from pydantic import BaseModel, ValidationError


# ── Output validation schema ─────────────────────────────────────────────────
class DateExtractionOutput(BaseModel):
    dates: list[str]  # ISO 8601 strings


# ── Default model ─────────────────────────────────────────────────────────────
DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a date extraction specialist. Extract ALL date references
from the provided text. Normalise each date to ISO 8601 format (YYYY-MM-DD).
For partial dates (e.g. "Q3 2024"), use the first day of the period (2024-07-01).
For relative dates, resolve relative to today if possible, otherwise keep the
natural language form.

Return ONLY a JSON object: {"dates": ["YYYY-MM-DD", ...]}
No prose, no explanation."""


def _call_bedrock(text: str, model_id: str) -> dict[str, Any]:
    """Call Bedrock converse API and return parsed JSON."""
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": text}]}],
        inferenceConfig={"maxTokens": 2048},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    return json.loads(reply)


def execute(inputs: dict) -> dict:
    """Extract dates from text using a Bedrock LLM."""
    raw_text = inputs["raw_text"]
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    raw_output = _call_bedrock(raw_text, model_id)

    # Validate output format
    try:
        validated = DateExtractionOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise ValueError(
            f"LLM output did not match expected schema: {exc}"
        ) from exc

    return validated.model_dump()


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
