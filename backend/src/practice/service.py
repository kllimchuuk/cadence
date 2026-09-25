import uuid
from typing import Annotated

from fastapi import Depends

from practice.exceptions import InvalidSessionStatusError, LearningSessionNotFoundError
from practice.models import LearningSession, SessionStatus
from practice.repository import LearningSessionRepository, get_practice_repository
from scenarios.config import get_scenario

_FINISHED_STATUSES = frozenset({SessionStatus.COMPLETED, SessionStatus.INCOMPLETE})


class PracticeService:
    def __init__(self, repository: LearningSessionRepository) -> None:
        self._repository = repository

    async def start_session(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> LearningSession:
        get_scenario(scenario_id)
        return await self._repository.create(user_id, scenario_id)

    async def get_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> LearningSession:
        record = await self._repository.get_by_id(session_id, user_id)
        if record is None:
            raise LearningSessionNotFoundError()
        return record

    async def list_sessions(self, user_id: uuid.UUID) -> list[LearningSession]:
        return await self._repository.get_by_user(user_id)

    async def finish_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        status: SessionStatus,
        transcript: list[object],
    ) -> LearningSession:
        self._require_finishable_status(status)

        record = await self.get_session(session_id, user_id)
        if record.ended_at is not None:
            return record
        return await self._repository.finish(record, status, transcript)

    @staticmethod
    def _require_finishable_status(status: SessionStatus) -> None:
        if status not in _FINISHED_STATUSES:
            raise InvalidSessionStatusError()


def get_practice_service(
    repository: Annotated[LearningSessionRepository, Depends(get_practice_repository)],
) -> PracticeService:
    return PracticeService(repository)
