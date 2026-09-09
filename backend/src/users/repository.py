import uuid
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from users.models import User, normalize_email


class UserRepository(CRUDRepository[User, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError()


class UserRepositoryImpl(CRUDRepositorySQLAlchemy[User, uuid.UUID], UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()


def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> UserRepository:
    return UserRepositoryImpl(session)
