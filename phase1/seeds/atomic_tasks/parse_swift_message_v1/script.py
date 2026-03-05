# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       parse_swift_message_v1
# input_schema:  {"swift_raw_text": "str"}
# output_schema: {"parsed_fields": "dict"}

import json
import re
import sys


# Common MT103/MT202 fields
_FIELD_NAMES = {
    "20": "transaction_reference",
    "21": "related_reference",
    "23B": "bank_operation_code",
    "32A": "value_date_currency_amount",
    "33B": "currency_original_amount",
    "50K": "ordering_customer",
    "50A": "ordering_institution",
    "52A": "ordering_institution_alt",
    "53A": "senders_correspondent",
    "56A": "intermediary",
    "57A": "account_with_institution",
    "59": "beneficiary_customer",
    "59A": "beneficiary_institution",
    "70": "remittance_information",
    "71A": "details_of_charges",
    "72": "sender_to_receiver_info",
}


def execute(inputs: dict) -> dict:
    """Parse SWIFT message fields (MT103/MT202) from raw text."""
    raw = inputs["swift_raw_text"]

    # SWIFT fields start with :<tag>:
    pattern = re.compile(r":(\d{2}[A-Z]?):(.+?)(?=\n:\d{2}[A-Z]?:|\Z)", re.DOTALL)
    matches = pattern.findall(raw)

    parsed: dict[str, str] = {}
    for tag, value in matches:
        field_name = _FIELD_NAMES.get(tag, f"field_{tag}")
        parsed[field_name] = value.strip()

    return {"parsed_fields": parsed}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
