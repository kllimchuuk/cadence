import uuid
from typing import Any

import pytest
from starlette.websockets import WebSocketDisconnect, WebSocketState

from orchestration.session_runner import DeltaHandler, SessionTurn
from practice.models import LearningSession
from realtime.websocket import PracticeSessionSocket
from users.models import User

ABNORMAL_CLOSURE_CODE = 1006
OPENING_TURN = SessionTurn(assistant_messages=("Hi!",), awaiting_user=True)
GOODBYE_TURN = SessionTurn(
    assistant_messages=("Thanks for practising!",), awaiting_user=False, completed=True
)


class DroppingWebSocket:
    def __init__(self, drop_on: dict[str, str] | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.application_state = WebSocketState.CONNECTED
        self.sent: list[dict[str, Any]] = []
        self._drop_on = drop_on

    async def accept(self) -> None:
        return None

    async def receive_json(self) -> dict[str, str]:
        return {"type": "end_session"}

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        if data == self._drop_on:
            self.application_state = WebSocketState.DISCONNECTED
            raise WebSocketDisconnect(code=ABNORMAL_CLOSURE_CODE)
        self.sent.append(data)

    async def close(self, code: int) -> None:
        self.application_state = WebSocketState.DISCONNECTED


class EndingSessionRunner:
    def __init__(self) -> None:
        self.abandoned = False

    async def create_session(
        self, user_id: uuid.UUID, scenario_id: str
    ) -> LearningSession:
        return LearningSession(
            id=uuid.uuid4(), user_id=user_id, scenario_id=scenario_id
        )

    async def open_conversation(
        self, learning_session: LearningSession, on_delta: DeltaHandler
    ) -> SessionTurn:
        return OPENING_TURN

    async def end_conversation(
        self, learning_session: LearningSession, on_delta: DeltaHandler
    ) -> SessionTurn:
        return GOODBYE_TURN

    async def abandon_session(self, learning_session: LearningSession) -> None:
        self.abandoned = True


class RecordingAnalysisRunner:
    def __init__(self) -> None:
        self.analysed: list[uuid.UUID] = []

    async def analyse(self, learning_session: LearningSession) -> tuple[str, ...]:
        self.analysed.append(learning_session.id)
        return ("Practice past-tense verbs",)


async def _run_until_goodbye(
    websocket: DroppingWebSocket,
    runner: EndingSessionRunner,
    analysis_runner: RecordingAnalysisRunner,
) -> None:
    socket = PracticeSessionSocket(websocket, runner, analysis_runner, [])
    await socket.run(User(id=uuid.uuid4()), "job_interview")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drop_on",
    [
        {"type": "assistant_done", "content": "Thanks for practising!"},
        {"type": "session_ended", "status": "completed"},
    ],
)
async def test_a_completed_session_is_analysed_even_if_the_goodbye_is_lost(
    drop_on: dict[str, str],
) -> None:
    websocket = DroppingWebSocket(drop_on)
    runner = EndingSessionRunner()
    analysis_runner = RecordingAnalysisRunner()

    await _run_until_goodbye(websocket, runner, analysis_runner)

    assert len(analysis_runner.analysed) == 1
    assert not runner.abandoned
    assert websocket.sent[-1] != {
        "type": "analysis_ready",
        "focus_points": ["Practice past-tense verbs"],
    }


@pytest.mark.asyncio
async def test_the_analysis_report_follows_a_delivered_goodbye() -> None:
    websocket = DroppingWebSocket()
    analysis_runner = RecordingAnalysisRunner()

    await _run_until_goodbye(websocket, EndingSessionRunner(), analysis_runner)

    assert [frame["type"] for frame in websocket.sent] == [
        "session_started",
        "assistant_done",
        "assistant_done",
        "session_ended",
        "analysis_ready",
    ]
