from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from progress.schemas import ProgressPublic
from progress.service import ProgressService, get_progress_service
from users.models import User

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressPublic)
async def get_progress(
    user: Annotated[User, Depends(get_current_user)],
    progress_service: Annotated[ProgressService, Depends(get_progress_service)],
) -> ProgressPublic:
    return ProgressPublic.model_validate(await progress_service.get_report(user.id))
