from datetime import UTC, datetime

from auth.constants import SESSION_TTL
from auth.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from auth.repository import UserSessionRepository
from core.security import hash_password, password_needs_rehash, verify_password
from users.models import User
from users.repository import UserRepository


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
    ) -> None:
        self._users = user_repository
        self._sessions = session_repository

    async def register(self, email: str, password: str) -> tuple[User, str]:
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError()

        user = await self._users.create(
            email=email, hashed_password=hash_password(password)
        )
        token, _ = await self._sessions.create(user.id, SESSION_TTL)
        return user, token

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self._users.get_by_email(email)

        if not verify_password(password, user.hashed_password if user else None):
            raise InvalidCredentialsError()

        if password_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        token, _ = await self._sessions.create(user.id, SESSION_TTL)
        return user, token

    async def logout(self, token: str) -> None:
        await self._sessions.delete_by_token(token)

    async def authenticate(self, token: str) -> User | None:
        record = await self._sessions.get_by_token(token)
        if record is None or record.expires_at < datetime.now(UTC):
            return None

        await self._sessions.extend(record, SESSION_TTL)
        return await self._users.get_by_id(record.user_id)
