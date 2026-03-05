# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       classify_url_failure_v1
# input_schema:  {"failed_urls": "list[str]", "error_map": "dict"}
# output_schema: {"failure_report": "dict"}

import json
import sys


_CATEGORIES = {
    "DNS_FAILURE": "dns",
    "TIMEOUT": "timeout",
    "SSL_ERROR": "ssl",
}


def _classify(reason: str) -> str:
    for prefix, category in _CATEGORIES.items():
        if reason.startswith(prefix):
            return category
    if reason.startswith("HTTP_4"):
        return "4xx"
    if reason.startswith("HTTP_5"):
        return "5xx"
    return "unknown"


def execute(inputs: dict) -> dict:
    """Classify failed URLs by failure reason."""
    error_map = inputs.get("error_map", {})

    failure_report: dict[str, str] = {}
    for url in inputs["failed_urls"]:
        reason = error_map.get(url, "UNKNOWN")
        failure_report[url] = _classify(reason)

    return {"failure_report": failure_report}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
