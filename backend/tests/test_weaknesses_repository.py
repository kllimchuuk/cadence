import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from practice.repository import LearningSessionRepositoryImpl
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepository, WeaknessRecordRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> WeaknessRecordRepository:
    return WeaknessRecordRepositoryImpl(session)


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
async def test_a_new_weakness_starts_in_the_new_state_with_no_streak(
    session: AsyncSession,
    repository: WeaknessRecordRepository,
    user_id: uuid.UUID,
) -> None:
    created = await repository.create(
        user_id, WeaknessCategory.GRAMMAR, "past_perfect_vs_simple"
    )
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_user_and_skill(
        user_id, WeaknessCategory.GRAMMAR, "past_perfect_vs_simple"
    )

    assert found is not None
    assert found.id == created.id
    assert found.state == WeaknessState.NEW
    assert found.clean_streak == 0


@pytest.mark.asyncio
async def test_a_weakness_is_not_visible_to_another_user(
    session: AsyncSession,
    repository: WeaknessRecordRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, WeaknessCategory.GRAMMAR, "filler_words")
    await session.commit()

    found = await repository.get_by_user_and_skill(
        other_user_id, WeaknessCategory.GRAMMAR, "filler_words"
    )
    assert found is None


@pytest.mark.asyncio
async def test_only_active_and_probation_weaknesses_are_returned(
    session: AsyncSession,
    repository: WeaknessRecordRepository,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    new_record = await repository.create(user_id, WeaknessCategory.GRAMMAR, "new_one")
    active_record = await repository.create(
        user_id, WeaknessCategory.VOCABULARY, "active_one"
    )
    probation_record = await repository.create(
        user_id, WeaknessCategory.FLUENCY, "probation_one"
    )
    mastered_record = await repository.create(
        user_id, WeaknessCategory.TASK_COMPLETION, "mastered_one"
    )
    await repository.update_state(active_record, WeaknessState.ACTIVE, 1, session_id)
    await repository.update_state(
        probation_record, WeaknessState.PROBATION, 2, session_id
    )
    await repository.update_state(
        mastered_record, WeaknessState.MASTERED, 3, session_id
    )
    await session.commit()

    found = {
        record.skill_key for record in await repository.get_active_for_user(user_id)
    }

    assert found == {"active_one", "probation_one"}
    assert new_record.skill_key not in found
    assert mastered_record.skill_key not in found


@pytest.mark.asyncio
async def test_updating_state_persists_streak_and_last_session(
    session: AsyncSession,
    repository: WeaknessRecordRepository,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    created = await repository.create(user_id, WeaknessCategory.GRAMMAR, "articles")

    updated = await repository.update_state(
        created, WeaknessState.ACTIVE, 2, session_id
    )

    assert updated.state == WeaknessState.ACTIVE
    assert updated.clean_streak == 2
    assert updated.last_session_id == session_id


@pytest.mark.asyncio
async def test_the_same_skill_cannot_be_recorded_twice_for_a_user(
    session: AsyncSession,
    repository: WeaknessRecordRepository,
    user_id: uuid.UUID,
) -> None:
    await repository.create(user_id, WeaknessCategory.GRAMMAR, "duplicate_skill")
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.create(user_id, WeaknessCategory.GRAMMAR, "duplicate_skill")
