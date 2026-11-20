import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from progress.metrics import SessionMetrics
from progress.models import SessionProgress


class SessionProgressRepository(ABC):
    @abstractmethod
    async def create(
        self, session_id: uuid.UUID, user_id: uuid.UUID, metrics: SessionMetrics
    ) -> SessionProgress:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_session_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionProgress | None:
        raise NotImplementedError()

    @abstractmethod
    async def list_oldest_first(self, user_id: uuid.UUID) -> list[SessionProgress]:
        raise NotImplementedError()


class SessionProgressRepositoryImpl(SessionProgressRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, session_id: uuid.UUID, user_id: uuid.UUID, metrics: SessionMetrics
    ) -> SessionProgress:
        record = SessionProgress(
            session_id=session_id, user_id=user_id, **asdict(metrics)
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_session_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionProgress | None:
        result = await self._session.execute(
            select(SessionProgress).where(
                SessionProgress.session_id == session_id,
                SessionProgress.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_oldest_first(self, user_id: uuid.UUID) -> list[SessionProgress]:
        result = await self._session.execute(
            select(SessionProgress)
            .where(SessionProgress.user_id == user_id)
            .order_by(SessionProgress.created_at, SessionProgress.id)
        )
        return list(result.scalars().all())


def get_progress_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SessionProgressRepository:
    return SessionProgressRepositoryImpl(session)
