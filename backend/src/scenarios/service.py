import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends

from analysis.models import SessionAnalysis
from analysis.repository import SessionAnalysisRepository, get_analysis_repository
from practice.repository import LearningSessionRepository, get_practice_repository
from scenarios.config import Scenario, list_scenarios
from scenarios.recommendation import recommend_scenario
from weaknesses.repository import WeaknessRecordRepository, get_weakness_repository


@dataclass(frozen=True)
class RecommendationReason:
    skill_key: str
    state: str
    evidence: str | None


@dataclass(frozen=True)
class ScenarioRecommendation:
    scenario: Scenario | None
    reasons: list[RecommendationReason]


def _latest_error_evidence(
    analyses_newest_first: list[SessionAnalysis], skill_key: str
) -> str | None:
    for analysis in analyses_newest_first:
        for observation in analysis.skill_observations:
            if (observation["skill_key"], observation["outcome"]) == (
                skill_key,
                "error",
            ):
                return observation["evidence"]
    return None


class ScenarioCatalogService:
    def list_scenarios(self) -> tuple[Scenario, ...]:
        return list_scenarios()


def get_scenario_catalog_service() -> ScenarioCatalogService:
    return ScenarioCatalogService()


class ScenarioRecommendationService:
    def __init__(
        self,
        weakness_repository: WeaknessRecordRepository,
        session_repository: LearningSessionRepository,
        analysis_repository: SessionAnalysisRepository,
    ) -> None:
        self._weaknesses = weakness_repository
        self._sessions = session_repository
        self._analyses = analysis_repository

    async def recommend(self, user_id: uuid.UUID) -> ScenarioRecommendation:
        weaknesses = await self._weaknesses.get_active_for_user(user_id)
        last_completed = await self._sessions.get_last_completed_at_by_scenario(user_id)

        match = recommend_scenario(weaknesses, last_completed)
        if match is None:
            return ScenarioRecommendation(scenario=None, reasons=[])

        analyses = await self._analyses.list_by_user(user_id)
        return ScenarioRecommendation(
            match.scenario,
            [
                RecommendationReason(
                    weakness.skill_key,
                    weakness.state,
                    _latest_error_evidence(analyses, weakness.skill_key),
                )
                for weakness in match.weaknesses
            ],
        )


def get_scenario_recommendation_service(
    weakness_repository: Annotated[
        WeaknessRecordRepository, Depends(get_weakness_repository)
    ],
    session_repository: Annotated[
        LearningSessionRepository, Depends(get_practice_repository)
    ],
    analysis_repository: Annotated[
        SessionAnalysisRepository, Depends(get_analysis_repository)
    ],
) -> ScenarioRecommendationService:
    return ScenarioRecommendationService(
        weakness_repository, session_repository, analysis_repository
    )
