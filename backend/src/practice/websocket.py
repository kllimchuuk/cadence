import logging
from json import JSONDecodeError

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from orchestration.session_runner import SessionRunner, SessionTurn
from practice.models import LearningSession
from practice.schemas import (
    AssistantMessage,
    SessionEnded,
    SessionStarted,
    UserMessage,
)
from scenarios.exceptions import UnknownScenarioError
from users.models import User

logger = logging.getLogger(__name__)

UNAUTHENTICATED_CLOSE_CODE = 4401
INVALID_REQUEST_CLOSE_CODE = 4400
INTERNAL_ERROR_CLOSE_CODE = 4500


class PracticeSessionSocket:
    def __init__(self, websocket: WebSocket, runner: SessionRunner) -> None:
        self._websocket = websocket
        self._runner = runner

    async def run(self, user: User | None, scenario_id: str) -> None:
        learning_session = await self._open(user, scenario_id)
        if learning_session is None:
            return

        await self._converse(learning_session)

    async def _open(
        self, user: User | None, scenario_id: str
    ) -> LearningSession | None:
        if user is None:
            await self._websocket.close(code=UNAUTHENTICATED_CLOSE_CODE)
            return None

        try:
            learning_session = await self._runner.create_session(user.id, scenario_id)
        except UnknownScenarioError:
            await self._websocket.close(code=INVALID_REQUEST_CLOSE_CODE)
            return None

        await self._websocket.accept()
        await self._send(SessionStarted(session_id=learning_session.id))
        return learning_session

    async def _converse(self, learning_session: LearningSession) -> None:
        try:
            await self._exchange_turns(learning_session)
        except WebSocketDisconnect:
            return
        except (ValidationError, JSONDecodeError):
            await self._websocket.close(code=INVALID_REQUEST_CLOSE_CODE)
        except Exception:
            logger.exception(
                "Practice session failed",
                extra={"session_id": str(learning_session.id)},
            )
            await self._websocket.close(code=INTERNAL_ERROR_CLOSE_CODE)
        else:
            await self._websocket.close()

    async def _exchange_turns(self, learning_session: LearningSession) -> None:
        turn = await self._runner.open_conversation(learning_session)
        await self._send_turn(turn)

        while turn.awaiting_user:
            user_turn = await self._receive_user_turn()
            turn = await self._runner.submit_turn(learning_session, user_turn)
            await self._send_turn(turn)

    async def _send_turn(self, turn: SessionTurn) -> None:
        for content in turn.assistant_messages:
            await self._send(AssistantMessage(content=content))
        if not turn.awaiting_user:
            await self._send(SessionEnded(focus_points=list(turn.focus_points)))

    async def _receive_user_turn(self) -> str:
        payload = await self._websocket.receive_json()
        return UserMessage.model_validate(payload).content

    async def _send(self, message: BaseModel) -> None:
        await self._websocket.send_json(message.model_dump(mode="json"))
