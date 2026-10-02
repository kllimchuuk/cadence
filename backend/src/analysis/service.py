import uuid
from typing import Annotated

from fastapi import Depends

from analysis.exceptions import InvalidFocusPointCountError
from analysis.models import SessionAnalysis
from analysis.repository import SessionAnalysisRepository, get_analysis_repository
from practice.exceptions import LearningSessionNotFoundError
from practice.repository import LearningSessionRepository, get_practice_repository

_MAX_FOCUS_POINTS = 3


class AnalysisService:
    def __init__(
        self,
        repository: SessionAnalysisRepository,
        session_repository: LearningSessionRepository,
    ) -> None:
        self._repository = repository
        self._sessions = session_repository

    async def create_analysis(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        grammar_findings: list[object],
        vocabulary_findings: list[object],
        fluency_findings: dict[str, object],
        task_completion: dict[str, object],
        focus_points: list[object],
    ) -> SessionAnalysis:
        await self._require_own_session(session_id, user_id)

        existing = await self._repository.get_by_session_id(session_id, user_id)
        if existing is not None:
            return existing

        self._require_valid_focus_point_count(focus_points)

        return await self._repository.create(
            session_id=session_id,
            user_id=user_id,
            grammar_findings=grammar_findings,
            vocabulary_findings=vocabulary_findings,
            fluency_findings=fluency_findings,
            task_completion=task_completion,
            focus_points=focus_points,
        )

    async def get_analysis(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionAnalysis | None:
        return await self._repository.get_by_session_id(session_id, user_id)

    async def list_analyses(self, user_id: uuid.UUID) -> list[SessionAnalysis]:
        return await self._repository.list_by_user(user_id)

    async def _require_own_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        if await self._sessions.get_by_id(session_id, user_id) is None:
            raise LearningSessionNotFoundError()

    @staticmethod
    def _require_valid_focus_point_count(focus_points: list[object]) -> None:
        if not 1 <= len(focus_points) <= _MAX_FOCUS_POINTS:
            raise InvalidFocusPointCountError()


def get_analysis_service(
    repository: Annotated[SessionAnalysisRepository, Depends(get_analysis_repository)],
    session_repository: Annotated[
        LearningSessionRepository, Depends(get_practice_repository)
    ],
) -> AnalysisService:
    return AnalysisService(repository, session_repository)
