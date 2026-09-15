import uuid
from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.models import SessionAnalysis
from core.database import get_db


class SessionAnalysisRepository(ABC):
    @abstractmethod
    async def create(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        grammar_findings: list[object],
        vocabulary_findings: list[object],
        fluency_findings: dict[str, object],
        task_completion: dict[str, object],
        focus_points: list[object],
    ) -> SessionAnalysis:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_session_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionAnalysis | None:
        raise NotImplementedError()

    @abstractmethod
    async def list_by_user(self, user_id: uuid.UUID) -> list[SessionAnalysis]:
        raise NotImplementedError()


class SessionAnalysisRepositoryImpl(SessionAnalysisRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        grammar_findings: list[object],
        vocabulary_findings: list[object],
        fluency_findings: dict[str, object],
        task_completion: dict[str, object],
        focus_points: list[object],
    ) -> SessionAnalysis:
        record = SessionAnalysis(
            session_id=session_id,
            user_id=user_id,
            grammar_findings=grammar_findings,
            vocabulary_findings=vocabulary_findings,
            fluency_findings=fluency_findings,
            task_completion=task_completion,
            focus_points=focus_points,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_session_id(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> SessionAnalysis | None:
        result = await self._session.execute(
            select(SessionAnalysis).where(
                SessionAnalysis.session_id == session_id,
                SessionAnalysis.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[SessionAnalysis]:
        result = await self._session.execute(
            select(SessionAnalysis).where(SessionAnalysis.user_id == user_id)
        )
        return list(result.scalars().all())


def get_analysis_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SessionAnalysisRepository:
    return SessionAnalysisRepositoryImpl(session)
