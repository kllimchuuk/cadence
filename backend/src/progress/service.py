import uuid
from typing import Annotated

from fastapi import Depends

from analysis.exceptions import SessionAnalysisNotFoundError
from analysis.repository import SessionAnalysisRepository, get_analysis_repository
from practice.exceptions import LearningSessionNotFoundError
from practice.repository import LearningSessionRepository, get_practice_repository
from progress.metrics import measure_session
from progress.models import SessionProgress
from progress.report import ProgressReport, build_report
from progress.repository import SessionProgressRepository, get_progress_repository


class ProgressService:
    def __init__(
        self,
        repository: SessionProgressRepository,
        analysis_repository: SessionAnalysisRepository,
        session_repository: LearningSessionRepository,
    ) -> None:
        self._repository = repository
        self._analyses = analysis_repository
        self._sessions = session_repository

    async def record_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionProgress:
        existing = await self._repository.get_by_session_id(session_id, user_id)
        if existing is not None:
            return existing

        learning_session = await self._sessions.get_by_id(session_id, user_id)
        if learning_session is None:
            raise LearningSessionNotFoundError()

        analysis = await self._analyses.get_by_session_id(session_id, user_id)
        if analysis is None:
            raise SessionAnalysisNotFoundError()

        return await self._repository.create(
            session_id, user_id, measure_session(learning_session, analysis)
        )

    async def get_report(self, user_id: uuid.UUID) -> ProgressReport:
        return build_report(await self._repository.list_oldest_first(user_id))


def get_progress_service(
    repository: Annotated[SessionProgressRepository, Depends(get_progress_repository)],
    analysis_repository: Annotated[
        SessionAnalysisRepository, Depends(get_analysis_repository)
    ],
    session_repository: Annotated[
        LearningSessionRepository, Depends(get_practice_repository)
    ],
) -> ProgressService:
    return ProgressService(repository, analysis_repository, session_repository)
