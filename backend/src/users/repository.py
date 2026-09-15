import uuid
from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from users.models import User, normalize_email


class UserRepository(CRUDRepository[User, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[User]:
        raise NotImplementedError()

    @abstractmethod
    async def get_all(self) -> list[User]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_google_sub(self, google_sub: str) -> User | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_nickname(self, nickname: str) -> User | None:
        raise NotImplementedError()

    @abstractmethod
    async def link_google_account(self, user: User, google_sub: str) -> None:
        raise NotImplementedError()


class UserRepositoryImpl(CRUDRepositorySQLAlchemy[User, uuid.UUID], UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[User]:
        result = await self._session.execute(select(User).where(User.id.in_(ids)))
        return list(result.scalars().all())

    async def get_all(self) -> list[User]:
        result = await self._session.execute(select(User))
        return list(result.scalars().all())

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.google_sub == google_sub)
        )
        return result.scalar_one_or_none()

    async def get_by_nickname(self, nickname: str) -> User | None:
        result = await self._session.execute(
            select(User).where(func.lower(User.nickname) == nickname.lower())
        )
        return result.scalar_one_or_none()

    async def link_google_account(self, user: User, google_sub: str) -> None:
        user.google_sub = google_sub
        await self._session.flush()


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRepository:
    return UserRepositoryImpl(session)
