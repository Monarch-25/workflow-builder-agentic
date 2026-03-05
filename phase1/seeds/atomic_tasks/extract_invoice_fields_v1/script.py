# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       extract_invoice_fields_v1
# input_schema:  {"raw_text": "str", "model_id": "str"}
# output_schema: {"vendor": "str", "date": "str", "total_amount": "float", "line_items": "list[dict]"}

import json
import os
import sys

import boto3
from pydantic import BaseModel, ValidationError


class LineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float


class InvoiceExtractionOutput(BaseModel):
    vendor: str
    date: str  # ISO 8601
    total_amount: float
    line_items: list[LineItem]


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT = """You are an invoice data extraction specialist. Extract all
structured fields from the invoice text provided.

Return ONLY a JSON object:
{
  "vendor": "Company Name",
  "date": "YYYY-MM-DD",
  "total_amount": 1500.00,
  "line_items": [
    {"description": "Widget", "quantity": 10, "unit_price": 100.0, "total": 1000.0}
  ]
}
No prose, no explanation."""


def execute(inputs: dict) -> dict:
    """Extract invoice fields using a Bedrock LLM."""
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
        inferenceConfig={"maxTokens": 4096},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    raw_output = json.loads(reply)

    try:
        validated = InvoiceExtractionOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise ValueError(f"LLM output did not match expected schema: {exc}") from exc

    return {
        "vendor": validated.vendor,
        "date": validated.date,
        "total_amount": validated.total_amount,
        "line_items": [item.model_dump() for item in validated.line_items],
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
