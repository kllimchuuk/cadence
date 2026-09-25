import uuid
from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from persona.models import PersonaMemory


class PersonaMemoryRepository(ABC):
    @abstractmethod
    async def create(
        self, user_id: uuid.UUID, scenario_id: str, facts: list[str]
    ) -> PersonaMemory:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_user_and_scenario(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> PersonaMemory | None:
        raise NotImplementedError()

    @abstractmethod
    async def update_facts(
        self, record: PersonaMemory, facts: list[str]
    ) -> PersonaMemory:
        raise NotImplementedError()


class PersonaMemoryRepositoryImpl(PersonaMemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: uuid.UUID, scenario_id: str, facts: list[str]
    ) -> PersonaMemory:
        record = PersonaMemory(user_id=user_id, scenario_id=scenario_id, facts=facts)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_user_and_scenario(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> PersonaMemory | None:
        result = await self._session.execute(
            select(PersonaMemory).where(
                PersonaMemory.user_id == user_id,
                PersonaMemory.scenario_id == scenario_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_facts(
        self, record: PersonaMemory, facts: list[str]
    ) -> PersonaMemory:
        record.facts = facts
        await self._session.flush()
        return record


def get_persona_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PersonaMemoryRepository:
    return PersonaMemoryRepositoryImpl(session)
