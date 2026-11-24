import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from practice.repository import LearningSessionRepositoryImpl
from progress.metrics import SessionMetrics
from progress.repository import SessionProgressRepository, SessionProgressRepositoryImpl
from users.repository import UserRepositoryImpl

METRICS = SessionMetrics(
    grammar_issue_count=2,
    vocabulary_issue_count=1,
    goals_achieved=3,
    goals_total=4,
    learner_word_count=120,
    total_word_count=300,
)


@pytest.fixture
def repository(session: AsyncSession) -> SessionProgressRepository:
    return SessionProgressRepositoryImpl(session)


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


async def _new_session_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    record = await LearningSessionRepositoryImpl(session).create(
        user_id, "job_interview"
    )
    return record.id


@pytest.mark.asyncio
async def test_progress_is_stored_and_read_back_by_session(
    session: AsyncSession, repository: SessionProgressRepository, user_id: uuid.UUID
) -> None:
    session_id = await _new_session_id(session, user_id)

    created = await repository.create(session_id, user_id, METRICS)
    found = await repository.get_by_session_id(session_id, user_id)

    assert found is not None
    assert found.id == created.id
    assert found.grammar_issue_count == 2
    assert found.learner_word_count == 120


@pytest.mark.asyncio
async def test_progress_is_not_visible_to_another_user(
    session: AsyncSession,
    repository: SessionProgressRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    session_id = await _new_session_id(session, user_id)
    await repository.create(session_id, user_id, METRICS)

    assert await repository.get_by_session_id(session_id, other_user_id) is None


@pytest.mark.asyncio
async def test_a_session_can_only_have_one_progress_row(
    session: AsyncSession, repository: SessionProgressRepository, user_id: uuid.UUID
) -> None:
    session_id = await _new_session_id(session, user_id)
    await repository.create(session_id, user_id, METRICS)

    with pytest.raises(IntegrityError):
        await repository.create(session_id, user_id, METRICS)


@pytest.mark.asyncio
async def test_progress_lists_oldest_first_and_only_the_users_own(
    session: AsyncSession,
    repository: SessionProgressRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    first_day = datetime(2026, 11, 1, tzinfo=UTC)
    created = []
    for day in (2, 0, 1):
        session_id = await _new_session_id(session, user_id)
        record = await repository.create(session_id, user_id, METRICS)
        record.created_at = first_day + timedelta(days=day)
        created.append(record)
    other_session_id = await _new_session_id(session, other_user_id)
    await repository.create(other_session_id, other_user_id, METRICS)
    await session.flush()

    found = await repository.list_oldest_first(user_id)

    assert [record.id for record in found] == [
        created[1].id,
        created[2].id,
        created[0].id,
    ]
