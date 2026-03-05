# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       classify_document_type_v1
# input_schema:  {"raw_text": "str", "model_id": "str"}
# output_schema: {"document_type": "str", "confidence": "float"}

import json
import os
import sys
from typing import Literal

import boto3
from pydantic import BaseModel, ValidationError


class DocumentClassificationOutput(BaseModel):
    document_type: Literal[
        "invoice", "contract", "report", "statement",
        "regulatory", "correspondence", "other"
    ]
    confidence: float


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a document classification specialist for banking
and financial services. Classify the document into exactly ONE of these types:
invoice, contract, report, statement, regulatory, correspondence, other.

Return ONLY a JSON object: {"document_type": "invoice", "confidence": 0.92}
No prose, no explanation."""


def execute(inputs: dict) -> dict:
    """Classify document type using a Bedrock LLM."""
    raw_text = inputs["raw_text"]
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    # Truncate to first 4000 chars for classification (sufficient context)
    text_sample = raw_text[:4000]

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": text_sample}]}],
        inferenceConfig={"maxTokens": 256},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    raw_output = json.loads(reply)

    try:
        validated = DocumentClassificationOutput.model_validate(raw_output)
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
