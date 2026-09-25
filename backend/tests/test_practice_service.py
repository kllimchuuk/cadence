import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from practice.exceptions import InvalidSessionStatusError, LearningSessionNotFoundError
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from scenarios.exceptions import UnknownScenarioError
from users.repository import UserRepositoryImpl


@pytest.fixture
def service(session: AsyncSession) -> PracticeService:
    return PracticeService(LearningSessionRepositoryImpl(session))


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
async def test_a_started_session_is_read_back_by_its_id(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    started = await service.start_session(user_id, "job_interview")

    found = await service.get_session(started.id, user_id)

    assert found.id == started.id
    assert found.status == SessionStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_starting_a_session_for_an_unknown_scenario_is_rejected(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    with pytest.raises(UnknownScenarioError):
        await service.start_session(user_id, "not_a_real_scenario")


@pytest.mark.asyncio
async def test_getting_an_unknown_session_raises_not_found(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.get_session(uuid.uuid4(), user_id)


@pytest.mark.asyncio
async def test_getting_another_users_session_raises_not_found(
    service: PracticeService, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    started = await service.start_session(user_id, "job_interview")

    with pytest.raises(LearningSessionNotFoundError):
        await service.get_session(started.id, other_user_id)


@pytest.mark.asyncio
async def test_listing_sessions_only_returns_the_users_own(
    service: PracticeService, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    await service.start_session(user_id, "job_interview")
    await service.start_session(other_user_id, "client_call")

    found = await service.list_sessions(user_id)

    assert {record.scenario_id for record in found} == {"job_interview"}


@pytest.mark.asyncio
async def test_finishing_a_session_sets_status_and_transcript(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    started = await service.start_session(user_id, "job_interview")
    transcript = [{"role": "agent", "text": "Tell me about yourself."}]

    finished = await service.finish_session(
        started.id, user_id, SessionStatus.COMPLETED, transcript
    )

    assert finished.status == SessionStatus.COMPLETED
    assert finished.transcript == transcript
    assert finished.ended_at is not None


@pytest.mark.asyncio
async def test_finishing_an_already_finished_session_is_a_no_op(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    started = await service.start_session(user_id, "job_interview")
    first_transcript = [{"role": "agent", "text": "Tell me about yourself."}]
    first = await service.finish_session(
        started.id, user_id, SessionStatus.COMPLETED, first_transcript
    )

    second = await service.finish_session(
        started.id, user_id, SessionStatus.INCOMPLETE, [{"role": "user", "text": "hi"}]
    )

    assert second.status == SessionStatus.COMPLETED
    assert second.transcript == first_transcript
    assert second.ended_at == first.ended_at


@pytest.mark.asyncio
async def test_finishing_with_in_progress_status_is_rejected(
    service: PracticeService, user_id: uuid.UUID
) -> None:
    started = await service.start_session(user_id, "job_interview")

    with pytest.raises(InvalidSessionStatusError):
        await service.finish_session(started.id, user_id, SessionStatus.IN_PROGRESS, [])
