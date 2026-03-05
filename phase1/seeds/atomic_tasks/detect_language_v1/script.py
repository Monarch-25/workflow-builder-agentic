# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       detect_language_v1
# input_schema:  {"raw_text": "str", "model_id": "str"}
# output_schema: {"language_code": "str", "confidence": "float"}

import json
import os
import sys

import boto3
from pydantic import BaseModel, ValidationError


class LanguageDetectionOutput(BaseModel):
    language_code: str  # ISO 639-1
    confidence: float   # 0.0 – 1.0


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a language detection specialist. Identify the language
of the provided text. Return the ISO 639-1 two-letter language code and your
confidence (0.0 to 1.0).

Return ONLY a JSON object: {"language_code": "en", "confidence": 0.95}
No prose, no explanation."""


def execute(inputs: dict) -> dict:
    """Detect language using a Bedrock LLM."""
    raw_text = inputs["raw_text"]
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": raw_text}]}],
        inferenceConfig={"maxTokens": 256},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    raw_output = json.loads(reply)

    try:
        validated = LanguageDetectionOutput.model_validate(raw_output)
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
