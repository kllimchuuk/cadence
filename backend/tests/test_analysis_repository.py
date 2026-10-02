import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.repository import SessionAnalysisRepository, SessionAnalysisRepositoryImpl
from practice.repository import LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> SessionAnalysisRepository:
    return SessionAnalysisRepositoryImpl(session)


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


@pytest_asyncio.fixture
async def session_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    record = await LearningSessionRepositoryImpl(session).create(
        user_id, "job_interview"
    )
    return record.id


def analysis_kwargs(session_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "grammar_findings": [{"error": "subject-verb agreement"}],
        "vocabulary_findings": [{"gap": "filler words"}],
        "fluency_findings": {"words_per_minute": 110},
        "task_completion": {"introduced_self": True},
        "focus_points": ["Practice past tense"],
    }


@pytest.mark.asyncio
async def test_an_analysis_is_created_and_read_back_by_session_id(
    session: AsyncSession,
    repository: SessionAnalysisRepository,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await repository.create(**analysis_kwargs(session_id, user_id))
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_session_id(session_id, user_id)

    assert found is not None
    assert found.grammar_findings == [{"error": "subject-verb agreement"}]
    assert found.fluency_findings == {"words_per_minute": 110}


@pytest.mark.asyncio
async def test_an_analysis_is_not_visible_to_another_user(
    session: AsyncSession,
    repository: SessionAnalysisRepository,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    await repository.create(**analysis_kwargs(session_id, user_id))
    await session.commit()

    assert await repository.get_by_session_id(session_id, other_user_id) is None


@pytest.mark.asyncio
async def test_analyses_are_listed_by_user(
    session: AsyncSession,
    repository: SessionAnalysisRepository,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await repository.create(**analysis_kwargs(session_id, user_id))
    await session.commit()

    found = await repository.list_by_user(user_id)

    assert len(found) == 1


@pytest.mark.asyncio
async def test_a_second_analysis_for_the_same_session_is_rejected(
    session: AsyncSession,
    repository: SessionAnalysisRepository,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await repository.create(**analysis_kwargs(session_id, user_id))
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.create(**analysis_kwargs(session_id, user_id))
