from typing import Literal

from pydantic import BaseModel, Field

from weaknesses.skill_keys import GrammarSkillKey

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
    skill_key: GrammarSkillKey
    outcome: Literal["error", "clean"]
    evidence: str = Field(description=EVIDENCE_DESCRIPTION)
    note: str


class GrammarTriage(BaseModel):
    skill_keys: list[GrammarSkillKey] = Field(
        description=(
            "Grammar skills in which the learner's turns show an error or a "
            "clear correct use."
        )
    )


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
