from typing import Literal

from pydantic import BaseModel

from weaknesses.models import WeaknessCategory


class SkillObservation(BaseModel):
    category: WeaknessCategory
    skill_key: str
    outcome: Literal["error", "clean"]
    note: str


class SessionAnalysisResult(BaseModel):
    grammar_findings: list[dict]
    vocabulary_findings: list[dict]
    fluency_findings: dict
    task_completion: dict
    focus_points: list[str]
    skill_observations: list[SkillObservation]
    new_facts: list[str]
