"""Tests for orchestration tool-spec compilation."""

from __future__ import annotations

import unittest

from phase2.orchestrator.tool_specs import (
    TOOL_SEARCH_TYPE,
    build_orchestrator_tools,
)
from phase2.tests.helpers import load_seed_tasks


class ToolSpecTests(unittest.TestCase):
    def test_non_anchor_tasks_are_deferred(self) -> None:
        tasks = load_seed_tasks(
            "upload_file_v1",
            "return_output_v1",
            "log_error_v1",
            "extract_text_from_pdf_v1",
        )
        tools = build_orchestrator_tools(tasks)

        self.assertEqual(tools[0]["type"], TOOL_SEARCH_TYPE)
        anchor = next(tool for tool in tools if tool.get("name") == "upload_file_v1")
        non_anchor = next(
            tool for tool in tools if tool.get("name") == "extract_text_from_pdf_v1"
        )

        self.assertNotIn("defer_loading", anchor)
        self.assertTrue(non_anchor["defer_loading"])


if __name__ == "__main__":
    unittest.main()

