import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from practice.exceptions import LearningSessionNotFoundError
from practice.repository import LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl
from weaknesses.exceptions import InvalidSkillKeyError
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl
from weaknesses.service import WeaknessService


@pytest.fixture
def service(session: AsyncSession) -> WeaknessService:
    return WeaknessService(
        WeaknessRecordRepositoryImpl(session), LearningSessionRepositoryImpl(session)
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


async def make_session(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    record = await LearningSessionRepositoryImpl(session).create(
        user_id, "job_interview"
    )
    return record.id


@pytest.mark.asyncio
async def test_recording_an_error_creates_an_active_record(
    service: WeaknessService, user_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    record = await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "past_perfect", session_id
    )

    assert record.state == WeaknessState.ACTIVE
    assert record.clean_streak == 0
    assert record.last_session_id == session_id


@pytest.mark.asyncio
async def test_recording_an_error_for_an_unknown_session_raises_not_found(
    service: WeaknessService, user_id: uuid.UUID
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.record_error(
            user_id, WeaknessCategory.GRAMMAR, "past_perfect", uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_recording_an_error_for_another_users_session_raises_not_found(
    service: WeaknessService,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.record_error(
            other_user_id, WeaknessCategory.GRAMMAR, "past_perfect", session_id
        )


@pytest.mark.asyncio
async def test_recording_an_error_with_a_blank_skill_key_is_rejected(
    service: WeaknessService, user_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    with pytest.raises(InvalidSkillKeyError):
        await service.record_error(user_id, WeaknessCategory.GRAMMAR, "  ", session_id)


@pytest.mark.asyncio
async def test_clean_use_for_a_never_erred_skill_is_a_no_op(
    service: WeaknessService, user_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    result = await service.record_clean_use(
        user_id, WeaknessCategory.GRAMMAR, "never_erred", session_id
    )

    assert result is None


@pytest.mark.asyncio
async def test_clean_use_in_the_same_session_does_not_advance_the_streak(
    session: AsyncSession,
    service: WeaknessService,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )

    first = await service.record_clean_use(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )
    second = await service.record_clean_use(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )

    assert first.clean_streak == second.clean_streak == 0


@pytest.mark.asyncio
async def test_enough_clean_sessions_advance_active_to_probation_to_mastered(
    session: AsyncSession,
    service: WeaknessService,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )

    record = None
    for _ in range(3):
        clean_session_id = await make_session(session, user_id)
        record = await service.record_clean_use(
            user_id, WeaknessCategory.GRAMMAR, "articles", clean_session_id
        )
    assert record.state == WeaknessState.PROBATION
    assert record.clean_streak == 0

    for _ in range(3):
        clean_session_id = await make_session(session, user_id)
        record = await service.record_clean_use(
            user_id, WeaknessCategory.GRAMMAR, "articles", clean_session_id
        )
    assert record.state == WeaknessState.MASTERED
    assert record.clean_streak == 0


@pytest.mark.asyncio
async def test_an_error_reopens_a_mastered_weakness(
    session: AsyncSession,
    service: WeaknessService,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )
    record = None
    for _ in range(6):
        clean_session_id = await make_session(session, user_id)
        record = await service.record_clean_use(
            user_id, WeaknessCategory.GRAMMAR, "articles", clean_session_id
        )
    assert record.state == WeaknessState.MASTERED

    relapse_session_id = await make_session(session, user_id)
    relapsed = await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "articles", relapse_session_id
    )

    assert relapsed.state == WeaknessState.ACTIVE
    assert relapsed.clean_streak == 0


@pytest.mark.asyncio
async def test_get_active_weaknesses_only_includes_active_and_probation(
    service: WeaknessService, user_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    await service.record_error(
        user_id, WeaknessCategory.GRAMMAR, "articles", session_id
    )

    active = await service.get_active_weaknesses(user_id)

    assert {record.skill_key for record in active} == {"articles"}
