import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.service import AnalysisService
from practice.exceptions import LearningSessionNotFoundError
from practice.repository import LearningSessionRepositoryImpl
from tests.fakes import analysis_result
from users.repository import UserRepositoryImpl


@pytest.fixture
def service(session: AsyncSession) -> AnalysisService:
    return AnalysisService(
        SessionAnalysisRepositoryImpl(session), LearningSessionRepositoryImpl(session)
    )


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


@pytest.mark.asyncio
async def test_an_analysis_is_created_and_read_back(
    service: AnalysisService, session_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    created = await service.create_analysis(session_id, user_id, analysis_result())

    found = await service.get_analysis(session_id, user_id)

    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_creating_for_an_unknown_session_raises_not_found(
    service: AnalysisService, user_id: uuid.UUID
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.create_analysis(uuid.uuid4(), user_id, analysis_result())


@pytest.mark.asyncio
async def test_creating_for_another_users_session_raises_not_found(
    service: AnalysisService,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.create_analysis(session_id, other_user_id, analysis_result())


@pytest.mark.asyncio
async def test_creating_twice_for_the_same_session_is_a_no_op(
    service: AnalysisService, session_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    first = await service.create_analysis(session_id, user_id, analysis_result())

    different = analysis_result().model_copy(
        update={"focus_points": ["Different point"]}
    )
    second = await service.create_analysis(session_id, user_id, different)

    assert second.id == first.id
    assert second.focus_points == ["Practice past-tense verbs"]


@pytest.mark.asyncio
async def test_getting_an_analysis_for_an_unanalyzed_session_returns_none(
    service: AnalysisService, session_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    assert await service.get_analysis(session_id, user_id) is None


@pytest.mark.asyncio
async def test_listing_analyses_only_returns_the_users_own(
    service: AnalysisService,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await service.create_analysis(session_id, user_id, analysis_result())

    found = await service.list_analyses(user_id)

    assert len(found) == 1
