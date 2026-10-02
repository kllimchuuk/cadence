import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from persona.exceptions import InvalidFactError
from persona.repository import PersonaMemoryRepositoryImpl
from persona.service import PersonaService
from users.repository import UserRepositoryImpl


@pytest.fixture
def service(session: AsyncSession) -> PersonaService:
    return PersonaService(PersonaMemoryRepositoryImpl(session))


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="learner@cadence.test",
        first_name="Learner",
        last_name="One",
        nickname="learner",
        hashed_password="hashed",
    )
    return user.id


@pytest.mark.asyncio
async def test_remembering_for_the_first_time_creates_the_memory(
    service: PersonaService, user_id: uuid.UUID
) -> None:
    memory = await service.remember(
        user_id, "job_interview", ["moving from backend to AI"]
    )

    assert memory.facts == ["moving from backend to AI"]


@pytest.mark.asyncio
async def test_remembering_again_merges_new_facts_without_duplicating(
    service: PersonaService, user_id: uuid.UUID
) -> None:
    await service.remember(user_id, "job_interview", ["moving from backend to AI"])

    updated = await service.remember(
        user_id,
        "job_interview",
        ["moving from backend to AI", "nervous about system design"],
    )

    assert updated.facts == [
        "moving from backend to AI",
        "nervous about system design",
    ]


@pytest.mark.asyncio
async def test_remembering_a_blank_fact_is_rejected(
    service: PersonaService, user_id: uuid.UUID
) -> None:
    with pytest.raises(InvalidFactError):
        await service.remember(user_id, "job_interview", ["  "])


@pytest.mark.asyncio
async def test_getting_memory_for_an_unseen_scenario_returns_none(
    service: PersonaService, user_id: uuid.UUID
) -> None:
    assert await service.get_memory(user_id, "client_call") is None
