import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnalysisOut(BaseModel):
    """The one analysis shape the frontend consumes, whichever path produced the decision."""

    pipeline_version: str
    source: str
    signal: dict[str, Any]
    processed: dict[str, Any]
    features: dict[str, Any]
    stages: list[dict[str, Any]]
    total_stage_ms: int
    metrics: list[dict[str, Any]]
    authentication: dict[str, Any]


class AttemptSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    result: str
    method: str
    processing_time_ms: int | None
    pipeline_version: str | None
    enrollment_reference: str | None
    has_analysis: bool


class AttemptDetail(AttemptSummary):
    analysis: AnalysisOut | None
    note: str | None = None
