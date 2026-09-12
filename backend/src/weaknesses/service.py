import uuid
from typing import Annotated

from fastapi import Depends

from practice.exceptions import LearningSessionNotFoundError
from practice.repository import LearningSessionRepository, get_practice_repository
from weaknesses.exceptions import InvalidSkillKeyError
from weaknesses.models import WeaknessCategory, WeaknessRecord, WeaknessState
from weaknesses.repository import WeaknessRecordRepository, get_weakness_repository

_CLEAN_STREAK_TO_ADVANCE = 3

_ADVANCE_ON_STREAK: dict[WeaknessState, WeaknessState] = {
    WeaknessState.NEW: WeaknessState.PROBATION,
    WeaknessState.ACTIVE: WeaknessState.PROBATION,
    WeaknessState.PROBATION: WeaknessState.MASTERED,
}


class WeaknessService:
    def __init__(
        self,
        repository: WeaknessRecordRepository,
        session_repository: LearningSessionRepository,
    ) -> None:
        self._repository = repository
        self._sessions = session_repository

    async def get_active_weaknesses(self, user_id: uuid.UUID) -> list[WeaknessRecord]:
        return await self._repository.get_active_for_user(user_id)

    async def record_error(
        self,
        user_id: uuid.UUID,
        category: WeaknessCategory,
        skill_key: str,
        session_id: uuid.UUID,
    ) -> WeaknessRecord:
        self._require_valid_skill_key(skill_key)
        await self._require_own_session(session_id, user_id)

        record = await self._get_or_create(user_id, category, skill_key)
        return await self._repository.update_state(
            record, WeaknessState.ACTIVE, clean_streak=0, last_session_id=session_id
        )

    async def record_clean_use(
        self,
        user_id: uuid.UUID,
        category: WeaknessCategory,
        skill_key: str,
        session_id: uuid.UUID,
    ) -> WeaknessRecord | None:
        self._require_valid_skill_key(skill_key)
        await self._require_own_session(session_id, user_id)

        record = await self._repository.get_by_user_and_skill(
            user_id, category, skill_key
        )
        if record is None or record.last_session_id == session_id:
            return record

        state, streak = self._advance(record.state, record.clean_streak + 1)
        return await self._repository.update_state(
            record, state, clean_streak=streak, last_session_id=session_id
        )

    async def _get_or_create(
        self, user_id: uuid.UUID, category: WeaknessCategory, skill_key: str
    ) -> WeaknessRecord:
        record = await self._repository.get_by_user_and_skill(
            user_id, category, skill_key
        )
        if record is not None:
            return record
        return await self._repository.create(user_id, category, skill_key)

    async def _require_own_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        if await self._sessions.get_by_id(session_id, user_id) is None:
            raise LearningSessionNotFoundError()

    @staticmethod
    def _require_valid_skill_key(skill_key: str) -> None:
        if not skill_key.strip():
            raise InvalidSkillKeyError()

    @staticmethod
    def _advance(state: WeaknessState, streak: int) -> tuple[WeaknessState, int]:
        next_state = _ADVANCE_ON_STREAK.get(state)
        if next_state is not None and streak >= _CLEAN_STREAK_TO_ADVANCE:
            return next_state, 0
        return state, streak


def get_weakness_service(
    repository: Annotated[WeaknessRecordRepository, Depends(get_weakness_repository)],
    session_repository: Annotated[
        LearningSessionRepository, Depends(get_practice_repository)
    ],
) -> WeaknessService:
    return WeaknessService(repository, session_repository)
