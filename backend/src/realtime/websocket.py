import asyncio
import logging
from json import JSONDecodeError

from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ValidationError
from starlette.websockets import WebSocketState

from orchestration.session_runner import SessionRunner, SessionTurn
from practice.exceptions import TooManyActiveSessionsError
from practice.models import LearningSession
from realtime.exceptions import PracticeSessionIdleError
from realtime.schemas import (
    CLIENT_MESSAGE_ADAPTER,
    AssistantMessage,
    ClientMessage,
    EndSession,
    InvalidMessage,
    SessionEnded,
    SessionStarted,
)
from scenarios.exceptions import UnknownScenarioError
from users.models import User

logger = logging.getLogger(__name__)

UNAUTHENTICATED_CLOSE_CODE = 4401
FORBIDDEN_ORIGIN_CLOSE_CODE = 4403
INVALID_REQUEST_CLOSE_CODE = 4400
IDLE_TIMEOUT_CLOSE_CODE = 4408
TOO_MANY_SESSIONS_CLOSE_CODE = 4429
INTERNAL_ERROR_CLOSE_CODE = 4500
IDLE_TIMEOUT_SECONDS = 300


class PracticeSessionSocket:
    def __init__(
        self,
        websocket: WebSocket,
        runner: SessionRunner,
        allowed_origins: list[str],
    ) -> None:
        self._websocket = websocket
        self._runner = runner
        self._allowed_origins = allowed_origins

    async def run(self, user: User | None, scenario_id: str) -> None:
        learning_session = await self._open(user, scenario_id)
        if learning_session is None:
            return

        await self._converse(learning_session)

    async def _open(
        self, user: User | None, scenario_id: str
    ) -> LearningSession | None:
        await self._websocket.accept()

        if not self._origin_allowed():
            await self._websocket.close(code=FORBIDDEN_ORIGIN_CLOSE_CODE)
            return None

        if user is None:
            await self._websocket.close(code=UNAUTHENTICATED_CLOSE_CODE)
            return None

        try:
            learning_session = await self._runner.create_session(user.id, scenario_id)
        except UnknownScenarioError:
            await self._websocket.close(code=INVALID_REQUEST_CLOSE_CODE)
            return None
        except TooManyActiveSessionsError:
            await self._websocket.close(code=TOO_MANY_SESSIONS_CLOSE_CODE)
            return None

        await self._send(SessionStarted(session_id=learning_session.id))
        return learning_session

    def _origin_allowed(self) -> bool:
        origin = self._websocket.headers.get("origin")
        return origin is None or origin in self._allowed_origins

    async def _converse(self, learning_session: LearningSession) -> None:
        try:
            await self._exchange_turns(learning_session)
        except WebSocketDisconnect:
            await self._abandon(learning_session)
        except PracticeSessionIdleError:
            await self._abandon_and_close(learning_session, IDLE_TIMEOUT_CLOSE_CODE)
        except Exception:
            logger.exception(
                "Practice session failed",
                extra={"session_id": str(learning_session.id)},
            )
            await self._abandon_and_close(learning_session, INTERNAL_ERROR_CLOSE_CODE)
        else:
            await self._close(status.WS_1000_NORMAL_CLOSURE)

    async def _abandon_and_close(
        self, learning_session: LearningSession, close_code: int
    ) -> None:
        try:
            await self._abandon(learning_session)
        finally:
            await self._close(close_code)

    async def _abandon(self, learning_session: LearningSession) -> None:
        await asyncio.shield(self._runner.abandon_session(learning_session))

    async def _close(self, close_code: int) -> None:
        if self._websocket.application_state == WebSocketState.CONNECTED:
            await self._websocket.close(code=close_code)

    async def _exchange_turns(self, learning_session: LearningSession) -> None:
        turn = await self._runner.open_conversation(learning_session)
        await self._send_turn(turn)

        while turn.awaiting_user:
            message = await self._receive_client_message()
            turn = await self._respond_to(learning_session, message)
            await self._send_turn(turn)

    async def _respond_to(
        self, learning_session: LearningSession, message: ClientMessage
    ) -> SessionTurn:
        if isinstance(message, EndSession):
            return await self._runner.end_conversation(learning_session)
        return await self._runner.submit_turn(learning_session, message.content)

    async def _send_turn(self, turn: SessionTurn) -> None:
        for content in turn.assistant_messages:
            await self._send(AssistantMessage(content=content))
        if not turn.awaiting_user:
            await self._send(SessionEnded(focus_points=list(turn.focus_points)))

    async def _receive_client_message(self) -> ClientMessage:
        try:
            async with asyncio.timeout(IDLE_TIMEOUT_SECONDS):
                return await self._receive_first_valid_message()
        except TimeoutError as error:
            raise PracticeSessionIdleError() from error

    async def _receive_first_valid_message(self) -> ClientMessage:
        while True:
            try:
                payload = await self._websocket.receive_json()
                return CLIENT_MESSAGE_ADAPTER.validate_python(payload)
            except (ValidationError, JSONDecodeError):
                await self._send(InvalidMessage())

    async def _send(self, message: BaseModel) -> None:
        await self._websocket.send_json(message.model_dump(mode="json"))
