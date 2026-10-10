from typing import Literal

from pydantic import BaseModel, Field

from weaknesses.models import WeaknessCategory

EVIDENCE_DESCRIPTION = "The learner's exact words from the transcript."


class LanguageFinding(BaseModel):
    evidence: str = Field(description=EVIDENCE_DESCRIPTION)
    issue: str
    correction: str


class FluencyAssessment(BaseModel):
    summary: str


class GoalOutcome(BaseModel):
    goal: str
    achieved: bool
    evidence: str = Field(description=EVIDENCE_DESCRIPTION)


class TaskCompletion(BaseModel):
    goals: list[GoalOutcome]


class SkillObservation(BaseModel):
    category: WeaknessCategory
    skill_key: str
    outcome: Literal["error", "clean"]
    evidence: str = Field(description=EVIDENCE_DESCRIPTION)
    note: str


class PersonaFact(BaseModel):
    fact: str
    evidence: str = Field(description=EVIDENCE_DESCRIPTION)


class SessionAnalysisResult(BaseModel):
    grammar_findings: list[LanguageFinding]
    vocabulary_findings: list[LanguageFinding]
    fluency_findings: FluencyAssessment
    task_completion: TaskCompletion
    focus_points: list[str] = Field(min_length=1, max_length=3)
    skill_observations: list[SkillObservation]
    new_facts: list[PersonaFact]
