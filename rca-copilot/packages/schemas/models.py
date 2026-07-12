from datetime import datetime

from pydantic import BaseModel, Field


class LogEvent(BaseModel):
    timestamp: datetime
    service: str
    level: str
    message: str = ""
    exception: str | None = None
    trace_id: str | None = None
    deployment_version: str | None = None


class AnalyzeRequest(BaseModel):
    events: list[LogEvent] = Field(..., description="Structured log events to analyze")


class Evidence(BaseModel):
    timestamp: datetime
    service: str
    message: str
    exception: str | None = None
    trace_id: str | None = None


class RCAReport(BaseModel):
    incident_summary: str
    suspected_root_cause: str
    confidence: int = Field(ge=0, le=100)
    affected_services: list[str]
    evidence: list[Evidence]
    recommended_next_steps: list[str]
    ai_explanation: str | None = None
    ai_recommended_next_steps: list[str] = Field(default_factory=list)
