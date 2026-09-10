import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from auth.repository import UserSessionRepository
from users.repository import UserRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> UserSessionRepository:
    return UserSessionRepository(session)


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="session-owner@cadence.test",
        first_name="Session",
        last_name="Owner",
        nickname="session-owner",
        hashed_password="hashed",
    )
    return user.id


@pytest.mark.asyncio
async def test_a_created_session_is_read_back_by_its_token(
    session: AsyncSession, repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    token, record = await repository.create(user_id, timedelta(days=30))
    await session.commit()

    found = await repository.get_by_token(token)

    assert found is not None
    assert found.token_hash == record.token_hash
    assert found.user_id == user_id


@pytest.mark.asyncio
async def test_an_unknown_token_reads_back_as_none(
    repository: UserSessionRepository,
) -> None:
    assert await repository.get_by_token("not-a-real-token") is None


@pytest.mark.asyncio
async def test_the_raw_token_is_never_persisted(
    session: AsyncSession, repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    token, record = await repository.create(user_id, timedelta(days=30))

    assert record.token_hash != token


@pytest.mark.asyncio
async def test_extending_a_session_pushes_its_expiry_forward(
    repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    _, record = await repository.create(user_id, timedelta(days=1))
    original_expiry = record.expires_at

    await repository.extend(record, timedelta(days=30))

    assert record.expires_at > original_expiry


@pytest.mark.asyncio
async def test_a_deleted_session_no_longer_reads_back(
    session: AsyncSession, repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    token, _ = await repository.create(user_id, timedelta(days=30))
    await session.commit()

    await repository.delete_by_token(token)
    await session.commit()

    assert await repository.get_by_token(token) is None


@pytest.mark.asyncio
async def test_deleting_an_unknown_token_does_not_raise(
    repository: UserSessionRepository,
) -> None:
    await repository.delete_by_token("not-a-real-token")


@pytest.mark.asyncio
async def test_a_session_is_deleted_when_its_user_is_deleted(
    session: AsyncSession, repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    token, _ = await repository.create(user_id, timedelta(days=30))
    await session.commit()

    user = await UserRepositoryImpl(session).get_by_id(user_id)
    await session.delete(user)
    await session.commit()
    session.expire_all()

    assert await repository.get_by_token(token) is None


@pytest.mark.asyncio
async def test_a_new_session_expires_after_its_ttl(
    repository: UserSessionRepository, user_id: uuid.UUID
) -> None:
    before = datetime.now(UTC)

    _, record = await repository.create(user_id, timedelta(days=30))

    assert record.expires_at > before + timedelta(days=29)
    assert record.expires_at < before + timedelta(days=31)
