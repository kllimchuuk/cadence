import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from persona.repository import PersonaMemoryRepository, PersonaMemoryRepositoryImpl
from users.repository import UserRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> PersonaMemoryRepository:
    return PersonaMemoryRepositoryImpl(session)


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


@pytest_asyncio.fixture
async def other_user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="other@cadence.test",
        first_name="Other",
        last_name="Learner",
        nickname="other-learner",
        hashed_password="hashed",
    )
    return user.id


@pytest.mark.asyncio
async def test_a_persona_memory_is_created_and_read_back(
    session: AsyncSession,
    repository: PersonaMemoryRepository,
    user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, "job_interview", ["moving from backend to AI"])
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_user_and_scenario(user_id, "job_interview")

    assert found is not None
    assert found.facts == ["moving from backend to AI"]


@pytest.mark.asyncio
async def test_a_persona_memory_is_not_visible_to_another_user(
    session: AsyncSession,
    repository: PersonaMemoryRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, "job_interview", ["moving from backend to AI"])
    await session.commit()

    assert (
        await repository.get_by_user_and_scenario(other_user_id, "job_interview")
        is None
    )


@pytest.mark.asyncio
async def test_updating_facts_replaces_the_list(
    session: AsyncSession,
    repository: PersonaMemoryRepository,
    user_id: uuid.UUID,
) -> None:
    created = await repository.create(user_id, "job_interview", ["first fact"])

    updated = await repository.update_facts(created, ["first fact", "second fact"])

    assert updated.facts == ["first fact", "second fact"]


@pytest.mark.asyncio
async def test_a_second_memory_for_the_same_scenario_is_rejected(
    session: AsyncSession,
    repository: PersonaMemoryRepository,
    user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, "job_interview", ["first fact"])
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.create(user_id, "job_interview", ["another fact"])
