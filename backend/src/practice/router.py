import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from analysis.service import AnalysisService, get_analysis_service
from auth.dependencies import get_current_user
from practice.models import LearningSession
from practice.schemas import SessionDetail, SessionSummary
from practice.service import PracticeService, get_practice_service
from users.models import User

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    user: Annotated[User, Depends(get_current_user)],
    practice_service: Annotated[PracticeService, Depends(get_practice_service)],
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LearningSession]:
    return await practice_service.list_sessions(user.id, limit, offset)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> SessionDetail:
    detail = await analysis_service.get_session_with_analysis(session_id, user.id)
    return SessionDetail.model_validate(detail)
