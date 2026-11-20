from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import get_websocket_user
from realtime.dependencies import get_practice_session_socket
from realtime.websocket import PracticeSessionSocket
from users.models import User

router = APIRouter(prefix="/practice", tags=["practice"])


@router.websocket("/sessions/ws")
async def practice_session_ws(
    scenario_id: str,
    user: Annotated[User | None, Depends(get_websocket_user)],
    socket: Annotated[PracticeSessionSocket, Depends(get_practice_session_socket)],
) -> None:
    await socket.run(user, scenario_id)
