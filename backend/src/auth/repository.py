import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import UserSession
from core.database import get_db
from core.security import generate_session_token, hash_session_token


class UserSessionRepository(ABC):
    @abstractmethod
    async def create(
        self, user_id: uuid.UUID, ttl: timedelta
    ) -> tuple[str, UserSession]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_token(self, token: str) -> UserSession | None:
        raise NotImplementedError()

    @abstractmethod
    async def extend(self, record: UserSession, ttl: timedelta) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def delete_by_token(self, token: str) -> None:
        raise NotImplementedError()


class UserSessionRepositoryImpl(UserSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: uuid.UUID, ttl: timedelta
    ) -> tuple[str, UserSession]:
        token = generate_session_token()
        record = UserSession(
            token_hash=hash_session_token(token),
            user_id=user_id,
            expires_at=datetime.now(UTC) + ttl,
        )
        self._session.add(record)
        await self._session.flush()
        return token, record

    async def get_by_token(self, token: str) -> UserSession | None:
        return await self._session.get(UserSession, hash_session_token(token))

    async def extend(self, record: UserSession, ttl: timedelta) -> None:
        record.expires_at = datetime.now(UTC) + ttl
        await self._session.flush()

    async def delete_by_token(self, token: str) -> None:
        await self._session.execute(
            delete(UserSession).where(
                UserSession.token_hash == hash_session_token(token)
            )
        )


def get_user_session_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSessionRepository:
    return UserSessionRepositoryImpl(session)
