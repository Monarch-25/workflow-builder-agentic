"""Lightweight trace recording for orchestrator turns."""

from __future__ import annotations

from .models import TraceEvent


class TraceRecorder:
    """Collect trace events while building a plan."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.events: list[TraceEvent] = []

    def add(self, stage: str, detail: str, **payload: object) -> None:
        """Record one trace event."""
        if not self.enabled:
            return
        self.events.append(
            TraceEvent(stage=stage, detail=detail, payload=dict(payload))
        )

