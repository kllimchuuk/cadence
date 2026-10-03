from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket

from auth.dependencies import get_optional_current_user
from orchestration.dependencies import get_session_runner
from orchestration.session_runner import SessionRunner
from practice.websocket import PracticeSessionSocket
from users.models import User

router = APIRouter(prefix="/practice", tags=["practice"])


@router.websocket("/sessions/ws")
async def practice_session_ws(
    websocket: WebSocket,
    scenario_id: str,
    user: Annotated[User | None, Depends(get_optional_current_user)],
    runner: Annotated[SessionRunner, Depends(get_session_runner)],
) -> None:
    await PracticeSessionSocket(websocket, runner).run(user, scenario_id)
