import uuid
from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from weaknesses.models import WeaknessCategory, WeaknessRecord, WeaknessState


class WeaknessRecordRepository(ABC):
    @abstractmethod
    async def create(
        self, user_id: uuid.UUID, category: WeaknessCategory, skill_key: str
    ) -> WeaknessRecord:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_user_and_skill(
        self, user_id: uuid.UUID, category: WeaknessCategory, skill_key: str
    ) -> WeaknessRecord | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_active_for_user(self, user_id: uuid.UUID) -> list[WeaknessRecord]:
        raise NotImplementedError()

    @abstractmethod
    async def update_state(
        self,
        record: WeaknessRecord,
        state: WeaknessState,
        clean_streak: int,
        last_session_id: uuid.UUID | None,
    ) -> WeaknessRecord:
        raise NotImplementedError()


class WeaknessRecordRepositoryImpl(WeaknessRecordRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: uuid.UUID, category: WeaknessCategory, skill_key: str
    ) -> WeaknessRecord:
        record = WeaknessRecord(user_id=user_id, category=category, skill_key=skill_key)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_user_and_skill(
        self, user_id: uuid.UUID, category: WeaknessCategory, skill_key: str
    ) -> WeaknessRecord | None:
        result = await self._session.execute(
            select(WeaknessRecord).where(
                WeaknessRecord.user_id == user_id,
                WeaknessRecord.category == category,
                WeaknessRecord.skill_key == skill_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: uuid.UUID) -> list[WeaknessRecord]:
        result = await self._session.execute(
            select(WeaknessRecord).where(
                WeaknessRecord.user_id == user_id,
                WeaknessRecord.state.in_(
                    [WeaknessState.ACTIVE, WeaknessState.PROBATION]
                ),
            )
        )
        return list(result.scalars().all())

    async def update_state(
        self,
        record: WeaknessRecord,
        state: WeaknessState,
        clean_streak: int,
        last_session_id: uuid.UUID | None,
    ) -> WeaknessRecord:
        record.state = state
        record.clean_streak = clean_streak
        record.last_session_id = last_session_id
        await self._session.flush()
        return record


def get_weakness_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WeaknessRecordRepository:
    return WeaknessRecordRepositoryImpl(session)
