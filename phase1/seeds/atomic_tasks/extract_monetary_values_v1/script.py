# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_monetary_values_v1
# input_schema:  {"raw_text": "str", "model_id": "str"}
# output_schema: {"monetary_values": "list[dict]"}

import json
import os
import sys
from typing import Any

import boto3
from pydantic import BaseModel, ValidationError


class MonetaryValue(BaseModel):
    amount: float
    currency: str  # ISO 4217 code, e.g. "USD", "EUR", "INR"


class MonetaryExtractionOutput(BaseModel):
    monetary_values: list[MonetaryValue]


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a financial data extraction specialist. Extract ALL
monetary amounts from the provided text. For each amount return the numeric
value and the ISO 4217 currency code.

Handle all formats: $1,234.56 → USD 1234.56, ₹10,00,000 → INR 1000000,
50 EUR → EUR 50, "1.5 million dollars" → USD 1500000.

Return ONLY a JSON object:
{"monetary_values": [{"amount": 1234.56, "currency": "USD"}, ...]}
No prose, no explanation."""


def _call_bedrock(text: str, model_id: str) -> dict[str, Any]:
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
    """Extract monetary values from text using a Bedrock LLM."""
    raw_text = inputs["raw_text"]
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    raw_output = _call_bedrock(raw_text, model_id)

    try:
        validated = MonetaryExtractionOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise ValueError(
            f"LLM output did not match expected schema: {exc}"
        ) from exc

    return {
        "monetary_values": [v.model_dump() for v in validated.monetary_values]
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
