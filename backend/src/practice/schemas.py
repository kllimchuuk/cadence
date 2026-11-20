import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from analysis.schemas import (
    FluencyAssessment,
    FocusPoint,
    LanguageFinding,
    TaskCompletion,
)
from practice.models import AnalysisStatus, SessionStatus


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scenario_id: str
    status: SessionStatus
    analysis_status: AnalysisStatus | None
    started_at: datetime
    ended_at: datetime | None


class TranscriptTurn(BaseModel):
    role: str
    content: str


class SessionWithTranscript(SessionSummary):
    transcript: list[TranscriptTurn] | None


class SessionAnalysisPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grammar_findings: list[LanguageFinding]
    vocabulary_findings: list[LanguageFinding]
    fluency_findings: FluencyAssessment
    task_completion: TaskCompletion
    focus_points: list[FocusPoint]


class SessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session: SessionWithTranscript
    analysis: SessionAnalysisPublic | None
