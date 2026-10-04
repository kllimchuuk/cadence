import asyncio
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
FORBIDDEN_ORIGIN_CLOSE_CODE = 4403
INVALID_REQUEST_CLOSE_CODE = 4400
IDLE_TIMEOUT_CLOSE_CODE = 4408
INTERNAL_ERROR_CLOSE_CODE = 4500
IDLE_TIMEOUT_SECONDS = 300


class _InvalidClientMessageError(Exception):
    pass


class _IdleTimeoutError(Exception):
    pass


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

        await self._send(SessionStarted(session_id=learning_session.id))
        return learning_session

    def _origin_allowed(self) -> bool:
        origin = self._websocket.headers.get("origin")
        return origin is None or origin in self._allowed_origins

    async def _converse(self, learning_session: LearningSession) -> None:
        try:
            await self._exchange_turns(learning_session)
        except WebSocketDisconnect:
            await asyncio.shield(self._runner.abandon_session(learning_session))
        except _InvalidClientMessageError:
            await self._abandon_and_close(learning_session, INVALID_REQUEST_CLOSE_CODE)
        except _IdleTimeoutError:
            await self._abandon_and_close(learning_session, IDLE_TIMEOUT_CLOSE_CODE)
        except Exception:
            logger.exception(
                "Practice session failed",
                extra={"session_id": str(learning_session.id)},
            )
            await self._abandon_and_close(learning_session, INTERNAL_ERROR_CLOSE_CODE)
        else:
            await self._websocket.close()

    async def _abandon_and_close(
        self, learning_session: LearningSession, close_code: int
    ) -> None:
        try:
            await self._runner.abandon_session(learning_session)
        finally:
            await self._websocket.close(code=close_code)

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
        try:
            payload = await asyncio.wait_for(
                self._websocket.receive_json(), IDLE_TIMEOUT_SECONDS
            )
            return UserMessage.model_validate(payload).content
        except TimeoutError as error:
            raise _IdleTimeoutError() from error
        except (ValidationError, JSONDecodeError) as error:
            raise _InvalidClientMessageError() from error

    async def _send(self, message: BaseModel) -> None:
        await self._websocket.send_json(message.model_dump(mode="json"))
