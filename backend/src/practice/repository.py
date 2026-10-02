import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from practice.models import LearningSession, SessionStatus


class LearningSessionRepository(ABC):
    @abstractmethod
    async def create(self, user_id: uuid.UUID, scenario_id: str) -> LearningSession:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> LearningSession | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_user(self, user_id: uuid.UUID) -> list[LearningSession]:
        raise NotImplementedError()

    @abstractmethod
    async def finish(
        self,
        record: LearningSession,
        status: SessionStatus,
        transcript: list[object],
    ) -> LearningSession:
        raise NotImplementedError()


class LearningSessionRepositoryImpl(LearningSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, scenario_id: str) -> LearningSession:
        record = LearningSession(user_id=user_id, scenario_id=scenario_id)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> LearningSession | None:
        result = await self._session.execute(
            select(LearningSession).where(
                LearningSession.id == session_id,
                LearningSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID) -> list[LearningSession]:
        result = await self._session.execute(
            select(LearningSession).where(LearningSession.user_id == user_id)
        )
        return list(result.scalars().all())

    async def finish(
        self,
        record: LearningSession,
        status: SessionStatus,
        transcript: list[object],
    ) -> LearningSession:
        record.status = status
        record.transcript = transcript
        record.ended_at = datetime.now(UTC)
        await self._session.flush()
        return record


def get_practice_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LearningSessionRepository:
    return LearningSessionRepositoryImpl(session)
