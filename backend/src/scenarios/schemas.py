from pydantic import BaseModel, ConfigDict

from weaknesses.models import WeaknessState


class ScenarioPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    persona: str
    goal_checklist: list[str]
    difficulty: str


class RecommendationReasonPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_key: str
    state: WeaknessState
    evidence: str | None


class ScenarioRecommendationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario: ScenarioPublic | None
    reasons: list[RecommendationReasonPublic]
