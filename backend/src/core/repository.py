from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_model import Base

T = TypeVar("T", bound=Base)
ID = TypeVar("ID")


class CRUDRepository(ABC, Generic[T, ID]):
    @abstractmethod
    async def get_by_id(self, id: ID) -> T | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_ids(self, ids: list[ID]) -> list[T]:
        raise NotImplementedError()

    @abstractmethod
    async def get_all(self) -> list[T]:
        raise NotImplementedError()

    @abstractmethod
    async def has(self, id: ID) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def create(self, **kwargs: object) -> T:
        raise NotImplementedError()

    @abstractmethod
    async def update(self, instance: T) -> T:
        raise NotImplementedError()

    @abstractmethod
    async def update_many(self, instances: list[T]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def delete(self, instance: T) -> None:
        raise NotImplementedError()


class CRUDRepositorySQLAlchemy(CRUDRepository[T, ID]):
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id: ID) -> T | None:
        return await self._session.get(self._model, id)

    async def get_by_ids(self, ids: list[ID]) -> list[T]:
        result = await self._session.execute(
            select(self._model).where(self._model.id.in_(ids))
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[T]:
        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())

    async def has(self, id: ID) -> bool:
        result = await self._session.execute(
            select(func.count(1)).where(self._model.id == id)
        )
        return result.scalar_one() > 0

    async def create(self, **kwargs: object) -> T:
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, instance: T) -> T:
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update_many(self, instances: list[T]) -> None:
        if not instances:
            return
        self._session.add_all(instances)
        await self._session.flush()

    async def delete(self, instance: T) -> None:
        await self._session.delete(instance)
        await self._session.flush()
