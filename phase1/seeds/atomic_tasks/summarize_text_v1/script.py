# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       summarize_text_v1
# input_schema:  {"raw_text": "str", "max_words": "int", "model_id": "str"}
# output_schema: {"summary": "str"}

import json
import os
import sys

import boto3
from pydantic import BaseModel, ValidationError


class SummarizationOutput(BaseModel):
    summary: str


DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-5"


def execute(inputs: dict) -> dict:
    """Summarise text using a Bedrock LLM."""
    raw_text = inputs["raw_text"]
    max_words = inputs.get("max_words", 150)
    model_id = inputs.get("model_id") or DEFAULT_MODEL_ID

    system_prompt = (
        f"You are a summarization expert. Summarize the following text "
        f"in at most {max_words} words. Be concise and preserve key facts. "
        f'Return ONLY a JSON object: {{"summary": "..."}}'
    )

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": raw_text}]}],
        inferenceConfig={"maxTokens": 2048},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    raw_output = json.loads(reply)

    try:
        validated = SummarizationOutput.model_validate(raw_output)
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
