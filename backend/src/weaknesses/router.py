from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from users.models import User
from weaknesses.schemas import WeaknessPublic
from weaknesses.service import WeaknessService, get_weakness_service

router = APIRouter(prefix="/weaknesses", tags=["weaknesses"])


@router.get("", response_model=list[WeaknessPublic])
async def list_weaknesses(
    user: Annotated[User, Depends(get_current_user)],
    weakness_service: Annotated[WeaknessService, Depends(get_weakness_service)],
) -> list[WeaknessPublic]:
    weaknesses = await weakness_service.list_weaknesses(user.id)
    return [WeaknessPublic.model_validate(weakness) for weakness in weaknesses]
