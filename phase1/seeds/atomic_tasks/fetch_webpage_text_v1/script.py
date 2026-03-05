# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       fetch_webpage_text_v1
# input_schema:  {"url": "str"}
# output_schema: {"text_content": "str", "title": "str", "status_code": "int"}

import json
import sys

import httpx
from bs4 import BeautifulSoup


def execute(inputs: dict) -> dict:
    """Fetch a webpage and extract visible text."""
    url = inputs["url"]

    response = httpx.get(url, follow_redirects=True, timeout=15)
    soup = BeautifulSoup(response.text, "lxml")

    # Remove script/style elements
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    return {
        "text_content": text,
        "title": title,
        "status_code": response.status_code,
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
