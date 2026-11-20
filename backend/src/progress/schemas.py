import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from progress.report import Direction


class SessionProgressPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    created_at: datetime
    grammar_issue_count: int
    vocabulary_issue_count: int
    goals_achieved: int
    goals_total: int
    learner_word_count: int
    total_word_count: int
    grammar_issue_rate: float
    vocabulary_issue_rate: float
    goal_completion_rate: float
    learner_word_share: float


class MetricTrendPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baseline: float
    latest: float
    direction: Direction


class ProgressTrendPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grammar_issue_rate: MetricTrendPublic | None
    vocabulary_issue_rate: MetricTrendPublic | None
    goal_completion_rate: MetricTrendPublic | None
    learner_word_share: MetricTrendPublic | None


class ProgressPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sessions: list[SessionProgressPublic]
    trend: ProgressTrendPublic
