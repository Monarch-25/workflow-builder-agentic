"""
AtomicTask — Pydantic model for a single self-contained task in the repo.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AtomicTask(BaseModel):
    """
    A single, self-contained processing step that the workflow engine
    can discover, chain, and execute.
    """

    task_id: str = Field(
        ...,
        description="Unique identifier, e.g. 'extract_text_from_pdf_v1'",
    )
    name: str = Field(
        ...,
        description="Human-readable label, e.g. 'Extract Text from PDF'",
    )
    description: str = Field(
        ...,
        description="What the task does — also used for RAG embedding",
    )

    # Schemas describe the dict keys expected / produced by execute()
    input_schema: dict = Field(
        default_factory=dict,
        description="Mapping of {field_name: type_hint} for expected inputs",
    )
    output_schema: dict = Field(
        default_factory=dict,
        description="Mapping of {field_name: type_hint} for guaranteed outputs",
    )

    script_path: str = Field(
        default="script.py",
        min_length=1,
        description=(
            "Relative path to script.py within the task directory "
            "(portable across machines)"
        ),
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="pip packages required by this task",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Searchable tags, e.g. ['pdf', 'text', 'extraction']",
    )

    author: str = "system"
    created_at: datetime = Field(default_factory=datetime.now)
    verified: bool = False
    version: int = 1
    usage_count: int = 0

    embedding: Optional[list[float]] = Field(
        default=None,
        description="Titan embedding vector of the description",
    )

    # 1-3 concrete input dicts shown to the LLM in tool specs
    usage_examples: list[dict] = Field(
        default_factory=list,
        description="Concrete invocation examples for the LLM",
    )
