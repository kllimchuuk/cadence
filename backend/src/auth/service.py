from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from auth.constants import SESSION_TTL
from auth.exceptions import (
    EmailAlreadyRegisteredError,
    GoogleAuthenticationError,
    InvalidCredentialsError,
    NicknameAlreadyTakenError,
)
from auth.nickname import generate_unique_nickname
from auth.repository import UserSessionRepository
from core.security import hash_password, password_needs_rehash, verify_password
from users.models import User
from users.repository import UserRepository

_NICKNAME_CONFLICT_RETRIES = 3

_CONFLICTING_UNIQUE_CONSTRAINTS: dict[str, type[Exception]] = {
    "ix_users_email": EmailAlreadyRegisteredError,
    "ix_users_nickname_lower": NicknameAlreadyTakenError,
    "ix_users_google_sub": GoogleAuthenticationError,
}


def _as_domain_conflict(error: IntegrityError) -> Exception:
    constraint = getattr(error.orig, "constraint_name", None)
    exception_type = _CONFLICTING_UNIQUE_CONSTRAINTS.get(constraint)
    return exception_type() if exception_type else error


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
    ) -> None:
        self._users = user_repository
        self._sessions = session_repository

    async def register(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        nickname: str,
    ) -> tuple[User, str]:
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError()
        if await self._users.get_by_nickname(nickname) is not None:
            raise NicknameAlreadyTakenError()

        user = await self._create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            nickname=nickname,
            hashed_password=hash_password(password),
        )
        return await self._issue_session(user)

    async def _create_user(self, **fields: object) -> User:
        try:
            return await self._users.create(**fields)
        except IntegrityError as error:
            raise _as_domain_conflict(error) from error

    async def _issue_session(self, user: User) -> tuple[User, str]:
        token, _ = await self._sessions.create(user.id, SESSION_TTL)
        return user, token

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self._users.get_by_email(email)

        if not verify_password(password, user.hashed_password if user else None):
            raise InvalidCredentialsError()

        if password_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        return await self._issue_session(user)

    async def logout(self, token: str | None) -> None:
        if token:
            await self._sessions.delete_by_token(token)

    async def authenticate(self, token: str) -> User | None:
        record = await self._sessions.get_by_token(token)
        if record is None or record.expires_at < datetime.now(UTC):
            return None

        if record.expires_at - datetime.now(UTC) < SESSION_TTL / 2:
            await self._sessions.extend(record, SESSION_TTL)

        return await self._users.get_by_id(record.user_id)

    async def login_with_google_userinfo(
        self, userinfo: Mapping[str, object]
    ) -> tuple[User, str]:
        return await self.login_with_google(
            google_sub=userinfo["sub"],
            email=userinfo["email"],
            given_name=userinfo.get("given_name", ""),
            family_name=userinfo.get("family_name", ""),
            email_verified=bool(userinfo.get("email_verified")),
        )

    async def login_with_google(
        self,
        google_sub: str,
        email: str,
        given_name: str,
        family_name: str,
        email_verified: bool = False,
    ) -> tuple[User, str]:
        user = await self._users.get_by_google_sub(google_sub)

        if user is None:
            user = await self._link_existing_google_account(
                email, google_sub, email_verified
            )

        if user is None:
            user = await self._register_google_user(
                email, given_name, family_name, google_sub
            )

        return await self._issue_session(user)

    async def _link_existing_google_account(
        self, email: str, google_sub: str, email_verified: bool
    ) -> User | None:
        existing_user = await self._users.get_by_email(email)
        if existing_user is None:
            return None

        if not email_verified:
            raise GoogleAuthenticationError()

        await self._users.link_google_account(existing_user, google_sub)
        return existing_user

    async def _register_google_user(
        self, email: str, given_name: str, family_name: str, google_sub: str
    ) -> User:
        base_nickname = given_name or email.split("@")[0]

        for _ in range(_NICKNAME_CONFLICT_RETRIES):
            nickname = await generate_unique_nickname(base_nickname, self._users)
            try:
                return await self._create_user(
                    email=email,
                    first_name=given_name,
                    last_name=family_name,
                    nickname=nickname,
                    google_sub=google_sub,
                )
            except NicknameAlreadyTakenError:
                continue

        raise NicknameAlreadyTakenError()
