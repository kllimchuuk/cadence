from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from auth.repository import UserSessionRepository
from auth.service import AuthService
from core.security import hash_password, verify_password
from users.repository import UserRepository


@pytest.fixture
def service(session: AsyncSession) -> AuthService:
    return AuthService(UserRepository(session), UserSessionRepository(session))


@pytest.mark.asyncio
async def test_registering_creates_a_user_with_a_hashed_password(
    service: AuthService,
) -> None:
    user, _ = await service.register("learner@cadence.test", "a-strong-password")

    assert user.email == "learner@cadence.test"
    assert user.hashed_password != "a-strong-password"
    assert verify_password("a-strong-password", user.hashed_password)


@pytest.mark.asyncio
async def test_registering_issues_a_working_session(service: AuthService) -> None:
    user, token = await service.register("learner@cadence.test", "a-strong-password")

    authenticated = await service.authenticate(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
async def test_registering_the_same_email_twice_is_rejected(
    service: AuthService,
) -> None:
    await service.register("taken@cadence.test", "a-strong-password")

    with pytest.raises(EmailAlreadyRegisteredError):
        await service.register("taken@cadence.test", "another-password")


@pytest.mark.asyncio
async def test_logging_in_with_the_right_password_succeeds(
    service: AuthService,
) -> None:
    await service.register("learner@cadence.test", "a-strong-password")

    user, token = await service.login("learner@cadence.test", "a-strong-password")

    assert user.email == "learner@cadence.test"
    assert await service.authenticate(token) is not None


@pytest.mark.asyncio
async def test_logging_in_with_the_wrong_password_is_rejected(
    service: AuthService,
) -> None:
    await service.register("learner@cadence.test", "a-strong-password")

    with pytest.raises(InvalidCredentialsError):
        await service.login("learner@cadence.test", "the-wrong-password")


@pytest.mark.asyncio
async def test_logging_in_as_an_unknown_user_is_rejected(
    service: AuthService,
) -> None:
    with pytest.raises(InvalidCredentialsError):
        await service.login("nobody@cadence.test", "whatever-password")


@pytest.mark.asyncio
async def test_an_unknown_user_and_a_wrong_password_fail_identically(
    service: AuthService,
) -> None:
    await service.register("learner@cadence.test", "a-strong-password")

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        await service.login("learner@cadence.test", "the-wrong-password")

    with pytest.raises(InvalidCredentialsError) as unknown_user:
        await service.login("nobody@cadence.test", "the-wrong-password")

    assert wrong_password.value.code == unknown_user.value.code
    assert wrong_password.value.message == unknown_user.value.message


@pytest.mark.asyncio
async def test_logging_out_invalidates_the_session(service: AuthService) -> None:
    _, token = await service.register("learner@cadence.test", "a-strong-password")

    await service.logout(token)

    assert await service.authenticate(token) is None


@pytest.mark.asyncio
async def test_logging_out_an_unknown_token_does_not_raise(
    service: AuthService,
) -> None:
    await service.logout("not-a-real-token")


@pytest.mark.asyncio
async def test_an_expired_session_does_not_authenticate(
    session: AsyncSession, service: AuthService
) -> None:
    user, _ = await service.register("learner@cadence.test", "a-strong-password")
    sessions = UserSessionRepository(session)
    token, _ = await sessions.create(user.id, timedelta(days=-1))

    assert await service.authenticate(token) is None


@pytest.mark.asyncio
async def test_authenticating_extends_the_session(
    session: AsyncSession, service: AuthService
) -> None:
    user, token = await service.register("learner@cadence.test", "a-strong-password")
    sessions = UserSessionRepository(session)
    record = await sessions.get_by_token(token)
    record.expires_at = datetime.now(UTC) + timedelta(days=1)

    await service.authenticate(token)

    refreshed = await sessions.get_by_token(token)
    assert refreshed.expires_at > datetime.now(UTC) + timedelta(days=29)


@pytest.mark.asyncio
async def test_a_stale_hash_is_upgraded_on_login(
    session: AsyncSession, service: AuthService
) -> None:
    repository = UserRepository(session)
    await repository.create(
        email="legacy@cadence.test",
        hashed_password=hash_password("a-strong-password"),
    )

    await service.login("legacy@cadence.test", "a-strong-password")

    upgraded = await repository.get_by_email("legacy@cadence.test")
    assert verify_password("a-strong-password", upgraded.hashed_password)
