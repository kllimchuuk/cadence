from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import (
    EmailAlreadyRegisteredError,
    GoogleAuthenticationError,
    InvalidCredentialsError,
    NicknameAlreadyTakenError,
)
from auth.nickname import generate_unique_nickname
from auth.repository import UserSessionRepository
from auth.service import AuthService
from core.security import hash_password, verify_password
from users.repository import UserRepositoryImpl


@pytest.fixture
def service(session: AsyncSession) -> AuthService:
    return AuthService(UserRepositoryImpl(session), UserSessionRepository(session))


@pytest.mark.asyncio
async def test_registering_creates_a_user_with_a_hashed_password(
    service: AuthService,
) -> None:
    user, _ = await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

    assert user.email == "learner@cadence.test"
    assert user.first_name == "Learner"
    assert user.last_name == "One"
    assert user.nickname == "learner"
    assert user.hashed_password != "a-strong-password"
    assert verify_password("a-strong-password", user.hashed_password)


@pytest.mark.asyncio
async def test_registering_issues_a_working_session(service: AuthService) -> None:
    user, token = await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

    authenticated = await service.authenticate(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
async def test_registering_the_same_email_twice_is_rejected(
    service: AuthService,
) -> None:
    await service.register(
        "taken@cadence.test", "a-strong-password", "Taken", "A", "taken-a"
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await service.register(
            "taken@cadence.test", "another-password", "Taken", "B", "taken-b"
        )


@pytest.mark.asyncio
async def test_registering_the_same_nickname_twice_is_rejected(
    service: AuthService,
) -> None:
    await service.register(
        "first@cadence.test", "a-strong-password", "First", "User", "shared-nick"
    )

    with pytest.raises(NicknameAlreadyTakenError):
        await service.register(
            "second@cadence.test",
            "another-password",
            "Second",
            "User",
            "shared-nick",
        )


@pytest.mark.asyncio
async def test_logging_in_with_the_right_password_succeeds(
    service: AuthService,
) -> None:
    await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

    user, token = await service.login("learner@cadence.test", "a-strong-password")

    assert user.email == "learner@cadence.test"
    assert await service.authenticate(token) is not None


@pytest.mark.asyncio
async def test_logging_in_with_the_wrong_password_is_rejected(
    service: AuthService,
) -> None:
    await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

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
    await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        await service.login("learner@cadence.test", "the-wrong-password")

    with pytest.raises(InvalidCredentialsError) as unknown_user:
        await service.login("nobody@cadence.test", "the-wrong-password")

    assert wrong_password.value.code == unknown_user.value.code
    assert wrong_password.value.message == unknown_user.value.message


@pytest.mark.asyncio
async def test_logging_out_invalidates_the_session(service: AuthService) -> None:
    _, token = await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )

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
    user, _ = await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )
    sessions = UserSessionRepository(session)
    token, _ = await sessions.create(user.id, timedelta(days=-1))

    assert await service.authenticate(token) is None


@pytest.mark.asyncio
async def test_authenticating_extends_the_session(
    session: AsyncSession, service: AuthService
) -> None:
    user, token = await service.register(
        "learner@cadence.test", "a-strong-password", "Learner", "One", "learner"
    )
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
    repository = UserRepositoryImpl(session)
    await repository.create(
        email="legacy@cadence.test",
        first_name="Legacy",
        last_name="User",
        nickname="legacy",
        hashed_password=hash_password("a-strong-password"),
    )

    await service.login("legacy@cadence.test", "a-strong-password")

    upgraded = await repository.get_by_email("legacy@cadence.test")
    assert verify_password("a-strong-password", upgraded.hashed_password)


@pytest.mark.asyncio
async def test_login_with_google_creates_a_new_user(service: AuthService) -> None:
    user, token = await service.login_with_google(
        "google-sub-1", "new-google-user@cadence.test", "Nikita", "Klimchuk"
    )

    assert user.email == "new-google-user@cadence.test"
    assert user.first_name == "Nikita"
    assert user.last_name == "Klimchuk"
    assert user.nickname == "Nikita"
    assert user.google_sub == "google-sub-1"
    assert user.hashed_password is None
    assert await service.authenticate(token) is not None


@pytest.mark.asyncio
async def test_login_with_google_reuses_the_same_user_on_repeat_sign_in(
    service: AuthService,
) -> None:
    first, _ = await service.login_with_google(
        "google-sub-2", "repeat@cadence.test", "Nikita", "Klimchuk"
    )

    second, _ = await service.login_with_google(
        "google-sub-2", "repeat@cadence.test", "Nikita", "Klimchuk"
    )

    assert first.id == second.id


@pytest.mark.asyncio
async def test_login_with_google_links_a_verified_existing_password_account(
    service: AuthService,
) -> None:
    password_user, _ = await service.register(
        "shared@cadence.test", "a-strong-password", "Shared", "User", "shared-nick"
    )

    linked_user, _ = await service.login_with_google(
        "google-sub-3",
        "shared@cadence.test",
        "Someone",
        "Else",
        email_verified=True,
    )

    assert linked_user.id == password_user.id
    assert linked_user.nickname == "shared-nick"
    assert linked_user.first_name == "Shared"
    assert linked_user.google_sub == "google-sub-3"
    assert linked_user.hashed_password is not None


@pytest.mark.asyncio
async def test_login_with_google_refuses_to_link_an_unverified_email(
    service: AuthService,
) -> None:
    await service.register(
        "unverified@cadence.test",
        "a-strong-password",
        "Shared",
        "User",
        "unverified-nick",
    )

    with pytest.raises(GoogleAuthenticationError):
        await service.login_with_google(
            "google-sub-5",
            "unverified@cadence.test",
            "Someone",
            "Else",
            email_verified=False,
        )


@pytest.mark.asyncio
async def test_login_with_google_derives_a_nickname_when_given_name_is_missing(
    service: AuthService,
) -> None:
    user, _ = await service.login_with_google(
        "google-sub-4", "no.name@cadence.test", "", ""
    )

    assert user.nickname == "noname"
    assert user.first_name == ""
    assert user.last_name == ""


@pytest.mark.asyncio
async def test_generate_unique_nickname_avoids_a_collision(
    session: AsyncSession,
) -> None:
    repository = UserRepositoryImpl(session)
    await repository.create(
        email="collider@cadence.test",
        first_name="Collider",
        last_name="User",
        nickname="nikita",
        hashed_password="hashed",
    )

    nickname = await generate_unique_nickname("Nikita", repository)

    assert nickname.lower() != "nikita"
    assert nickname.lower().startswith("nikita-")
