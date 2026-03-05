# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       render_html_report_v1
# input_schema:  {"template_path": "str", "context_data": "dict"}
# output_schema: {"output_path": "str"}

import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def execute(inputs: dict) -> dict:
    """Render a Jinja2 HTML template with context data."""
    template_path = Path(inputs["template_path"])
    context_data = inputs["context_data"]

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=True,
    )
    template = env.get_template(template_path.name)
    rendered = template.render(**context_data)

    output_path = str(template_path.parent / f"{template_path.stem}_rendered.html")
    Path(output_path).write_text(rendered)

    return {"output_path": output_path}


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
