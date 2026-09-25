import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from practice.models import SessionStatus
from practice.repository import LearningSessionRepository, LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> LearningSessionRepository:
    return LearningSessionRepositoryImpl(session)


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
async def test_a_created_session_is_read_back_by_its_id(
    session: AsyncSession,
    repository: LearningSessionRepository,
    user_id: uuid.UUID,
) -> None:
    created = await repository.create(user_id, "job_interview")
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_id(created.id, user_id)

    assert found is not None
    assert found.scenario_id == "job_interview"
    assert found.status == SessionStatus.IN_PROGRESS
    assert found.transcript is None
    assert found.started_at is not None
    assert found.ended_at is None


@pytest.mark.asyncio
async def test_a_session_is_not_visible_to_another_user(
    session: AsyncSession,
    repository: LearningSessionRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    created = await repository.create(user_id, "job_interview")
    await session.commit()

    assert await repository.get_by_id(created.id, other_user_id) is None


@pytest.mark.asyncio
async def test_sessions_are_read_back_by_user(
    session: AsyncSession,
    repository: LearningSessionRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, "job_interview")
    await repository.create(user_id, "daily_standup")
    await repository.create(other_user_id, "client_call")
    await session.commit()

    found = await repository.get_by_user(user_id)

    assert {record.scenario_id for record in found} == {
        "job_interview",
        "daily_standup",
    }


@pytest.mark.asyncio
async def test_finishing_a_session_sets_status_transcript_and_ended_at(
    session: AsyncSession,
    repository: LearningSessionRepository,
    user_id: uuid.UUID,
) -> None:
    created = await repository.create(user_id, "job_interview")
    transcript = [{"role": "agent", "text": "Tell me about yourself."}]

    finished = await repository.finish(created, SessionStatus.COMPLETED, transcript)

    assert finished.status == SessionStatus.COMPLETED
    assert finished.transcript == transcript
    assert finished.ended_at is not None


@pytest.mark.asyncio
async def test_an_unknown_id_reads_back_as_none(
    repository: LearningSessionRepository, user_id: uuid.UUID
) -> None:
    assert await repository.get_by_id(uuid.uuid4(), user_id) is None
