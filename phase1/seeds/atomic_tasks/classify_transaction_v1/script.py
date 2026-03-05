# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       classify_transaction_v1
# input_schema:  {"description": "str", "amount": "float", "categories": "list[str]", "model_id": "str"}
# output_schema: {"category": "str", "confidence": "float"}

import json
import os
import sys

import boto3
from pydantic import BaseModel, ValidationError


class TransactionClassificationOutput(BaseModel):
    category: str
    confidence: float


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT_TEMPLATE = """You are a banking transaction classifier. Classify the
transaction into exactly ONE of these categories: {categories}.

Transaction description: "{description}"
Amount: {amount}

Return ONLY a JSON object: {{"category": "...", "confidence": 0.95}}
The category MUST be one of the provided options. No prose."""


def execute(inputs: dict) -> dict:
    """Classify transaction using a Bedrock LLM."""
    description = inputs["description"]
    amount = inputs["amount"]
    categories = inputs["categories"]
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        categories=", ".join(categories),
        description=description,
        amount=amount,
    )

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[{"text": "You are a banking transaction classification specialist."}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 256},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    raw_output = json.loads(reply)

    try:
        validated = TransactionClassificationOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise ValueError(f"LLM output did not match expected schema: {exc}") from exc

    if validated.category not in categories:
        raise ValueError(
            f"LLM returned category '{validated.category}' which is not in {categories}"
        )

    return validated.model_dump()


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
