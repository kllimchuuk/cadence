import asyncio
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any, TypeVar

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.websockets import WebSocketDisconnect

from config import Settings
from core.database import build_engine, build_session_factory
from llm.dependencies import get_llm_client_factory
from main import create_app
from orchestration.nodes import conversing as conversing_node_module
from orchestration.schemas import SessionAnalysisResult
from practice import websocket as websocket_module
from practice.models import LearningSession, SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.schemas import MAX_USER_TURN_LENGTH
from practice.websocket import (
    FORBIDDEN_ORIGIN_CLOSE_CODE,
    IDLE_TIMEOUT_CLOSE_CODE,
    INTERNAL_ERROR_CLOSE_CODE,
    INVALID_REQUEST_CLOSE_CODE,
    TOO_MANY_SESSIONS_CLOSE_CODE,
    UNAUTHENTICATED_CLOSE_CODE,
)
from tests.helpers import settings_kwargs

POLL_TIMEOUT_SECONDS = 3
POLL_INTERVAL_SECONDS = 0.05
END_SESSION_FRAME = {"type": "end_session"}
USER_MESSAGE_FRAME = {"type": "user_message", "content": "Sure, let's continue."}

Polled = TypeVar("Polled")


def unique_email() -> str:
    return f"{uuid.uuid4()}@cadence.example"


def unique_nickname() -> str:
    return f"learner{uuid.uuid4().hex[:12]}"


def register_payload(**overrides: str) -> dict:
    payload = {
        "email": unique_email(),
        "password": "a-strong-password",
        "first_name": "Test",
        "last_name": "User",
        "nickname": unique_nickname(),
    }
    payload.update(overrides)
    return payload


class _FakeDualClient:
    def __init__(self, reply: str, analysis_result: SessionAnalysisResult) -> None:
        self._reply = reply
        self._analysis_result = analysis_result

    async def generate(self, _prompt: str) -> str:
        return self._reply

    async def generate_structured(
        self, _prompt: str, _schema: type
    ) -> SessionAnalysisResult:
        return self._analysis_result


class _FakeLLMClientFactory:
    def __init__(self, reply: str, analysis_result: SessionAnalysisResult) -> None:
        self._reply = reply
        self._analysis_result = analysis_result

    def create(self, _model: str) -> _FakeDualClient:
        return _FakeDualClient(self._reply, self._analysis_result)


class _FailingLLMClient:
    async def generate(self, _prompt: str) -> str:
        raise RuntimeError("the model is unavailable")


class _FailingLLMClientFactory:
    def create(self, _model: str) -> _FailingLLMClient:
        return _FailingLLMClient()


def _default_analysis_result() -> SessionAnalysisResult:
    return SessionAnalysisResult(
        grammar_findings=[],
        vocabulary_findings=[],
        fluency_findings={},
        task_completion={},
        focus_points=["Practice past-tense verbs"],
        skill_observations=[],
        new_facts=[],
    )


def _fetch_session(
    database_url: str, session_id: uuid.UUID, user_id: uuid.UUID
) -> LearningSession | None:
    async def query() -> LearningSession | None:
        engine = build_engine(database_url)
        try:
            async with build_session_factory(engine)() as session:
                return await LearningSessionRepositoryImpl(session).get_by_id(
                    session_id, user_id
                )
        finally:
            await engine.dispose()

    return asyncio.run(query())


def _checkpoint_count(database_url: str, session_id: uuid.UUID) -> int:
    async def query() -> int:
        engine = build_engine(database_url)
        try:
            async with engine.connect() as connection:
                return await connection.scalar(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :id"),
                    {"id": str(session_id)},
                )
        finally:
            await engine.dispose()

    return asyncio.run(query())


def _wait_until(
    read: Callable[[], Polled], is_done: Callable[[Polled], bool]
) -> Polled:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    value = read()
    while not is_done(value) and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        value = read()
    return value


def _wait_for_status(
    database_url: str,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    session_status: SessionStatus,
) -> LearningSession | None:
    return _wait_until(
        lambda: _fetch_session(database_url, session_id, user_id),
        lambda record: record is None or record.status == session_status,
    )


def _wait_for_forgotten_checkpoints(database_url: str, session_id: uuid.UUID) -> int:
    return _wait_until(
        lambda: _checkpoint_count(database_url, session_id),
        lambda count: count == 0,
    )


@pytest.fixture
def client(migrated_schema: str) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        **settings_kwargs(DATABASE_URL=migrated_schema, SECURE_COOKIES="false"),
    )
    app = create_app(settings)
    app.dependency_overrides[get_llm_client_factory] = lambda: _FakeLLMClientFactory(
        "Great, tell me more.", _default_analysis_result()
    )

    with TestClient(app) as test_client:
        yield test_client


def test_connecting_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == UNAUTHENTICATED_CLOSE_CODE


def test_connecting_from_a_foreign_origin_is_rejected(client: TestClient) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview",
        headers={"origin": "https://evil.example"},
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == FORBIDDEN_ORIGIN_CLOSE_CODE


def test_connecting_from_an_allowed_origin_starts_the_session(
    client: TestClient,
) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview",
        headers={"origin": "http://localhost:5173"},
    ) as ws:
        assert ws.receive_json()["type"] == "session_started"


def test_connecting_with_an_unknown_scenario_is_rejected(client: TestClient) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=not-a-scenario"
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == INVALID_REQUEST_CLOSE_CODE


@pytest.mark.parametrize(
    "send_invalid_frame",
    [
        lambda ws: ws.send_json({"type": "user_message"}),
        lambda ws: ws.send_json({"type": "unknown"}),
        lambda ws: ws.send_json(
            {"type": "user_message", "content": "a" * (MAX_USER_TURN_LENGTH + 1)}
        ),
        lambda ws: ws.send_text("not json"),
    ],
)
def test_an_invalid_frame_is_rejected_without_ending_the_conversation(
    client: TestClient,
    send_invalid_frame: Callable[[Any], None],
) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        ws.receive_json()
        ws.receive_json()
        send_invalid_frame(ws)
        rejected = ws.receive_json()
        ws.send_json(USER_MESSAGE_FRAME)
        reply = ws.receive_json()

    assert rejected == {"type": "invalid_message"}
    assert reply["type"] == "assistant_message"


def test_opening_more_sessions_than_allowed_at_once_is_rejected(
    client: TestClient,
) -> None:
    client.post("/auth/register", json=register_payload())
    url = "/practice/sessions/ws?scenario_id=job_interview"

    with client.websocket_connect(url) as first, client.websocket_connect(
        url
    ) as second:
        first.receive_json()
        second.receive_json()
        with client.websocket_connect(url) as third:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                third.receive_json()

    assert exc_info.value.code == TOO_MANY_SESSIONS_CLOSE_CODE


def test_an_internal_failure_closes_the_socket_and_abandons_the_session(
    client: TestClient,
    migrated_schema: str,
) -> None:
    client.app.dependency_overrides[get_llm_client_factory] = (
        lambda: _FailingLLMClientFactory()
    )
    register_response = client.post("/auth/register", json=register_payload())
    user_id = uuid.UUID(register_response.json()["id"])

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        session_id = uuid.UUID(ws.receive_json()["session_id"])
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == INTERNAL_ERROR_CLOSE_CODE
    abandoned = _wait_for_status(
        migrated_schema, session_id, user_id, SessionStatus.INCOMPLETE
    )
    assert abandoned is not None
    assert abandoned.status == SessionStatus.INCOMPLETE


def test_an_idle_connection_is_closed_with_a_timeout_code(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(websocket_module, "IDLE_TIMEOUT_SECONDS", 0.05)
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        ws.receive_json()
        ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == IDLE_TIMEOUT_CLOSE_CODE


def test_a_full_conversation_completes_with_focus_points(
    client: TestClient,
    migrated_schema: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conversing_node_module, "MAX_CONVERSATION_TURNS", 2)
    register_response = client.post("/auth/register", json=register_payload())
    user_id = uuid.UUID(register_response.json()["id"])

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        started = ws.receive_json()
        assert started["type"] == "session_started"
        session_id = uuid.UUID(started["session_id"])

        opening = ws.receive_json()
        assert opening["type"] == "assistant_message"

        for _ in range(conversing_node_module.MAX_CONVERSATION_TURNS):
            ws.send_json(USER_MESSAGE_FRAME)

        ended = None
        for _ in range(10):
            frame = ws.receive_json()
            if frame["type"] == "session_ended":
                ended = frame
                break

        assert ended is not None
        assert 1 <= len(ended["focus_points"]) <= 3

    finished = _fetch_session(migrated_schema, session_id, user_id)
    assert finished is not None
    assert finished.status == SessionStatus.COMPLETED
    assert _checkpoint_count(migrated_schema, session_id) == 0


def test_disconnecting_mid_conversation_marks_the_session_incomplete(
    client: TestClient,
    migrated_schema: str,
) -> None:
    register_response = client.post("/auth/register", json=register_payload())
    user_id = uuid.UUID(register_response.json()["id"])

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        started = ws.receive_json()
        session_id = uuid.UUID(started["session_id"])
        ws.receive_json()

    abandoned = _wait_for_status(
        migrated_schema, session_id, user_id, SessionStatus.INCOMPLETE
    )
    assert abandoned is not None
    assert abandoned.status == SessionStatus.INCOMPLETE
    assert abandoned.transcript is not None
    assert abandoned.transcript[0]["role"] == "assistant"
    assert _wait_for_forgotten_checkpoints(migrated_schema, session_id) == 0


def test_an_open_socket_does_not_hold_a_database_connection(
    client: TestClient,
) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        ws.receive_json()
        ws.receive_json()

        assert client.app.state.db_engine.pool.checkedout() == 0


def test_ending_the_session_after_a_turn_completes_it_with_focus_points(
    client: TestClient,
    migrated_schema: str,
) -> None:
    register_response = client.post("/auth/register", json=register_payload())
    user_id = uuid.UUID(register_response.json()["id"])

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        session_id = uuid.UUID(ws.receive_json()["session_id"])
        ws.receive_json()
        ws.send_json(USER_MESSAGE_FRAME)
        assert ws.receive_json()["type"] == "assistant_message"
        assert _checkpoint_count(migrated_schema, session_id) > 0

        ws.send_json(END_SESSION_FRAME)
        assert ws.receive_json()["type"] == "assistant_message"
        ended = ws.receive_json()

    assert ended == {
        "type": "session_ended",
        "focus_points": ["Practice past-tense verbs"],
    }
    finished = _fetch_session(migrated_schema, session_id, user_id)
    assert finished is not None
    assert finished.status == SessionStatus.COMPLETED
    assert _checkpoint_count(migrated_schema, session_id) == 0


def test_ending_the_session_before_speaking_marks_it_incomplete(
    client: TestClient,
    migrated_schema: str,
) -> None:
    register_response = client.post("/auth/register", json=register_payload())
    user_id = uuid.UUID(register_response.json()["id"])

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        session_id = uuid.UUID(ws.receive_json()["session_id"])
        ws.receive_json()
        ws.send_json(END_SESSION_FRAME)
        ended = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert ended == {"type": "session_ended", "focus_points": []}
    assert exc_info.value.code == status.WS_1000_NORMAL_CLOSURE
    abandoned = _fetch_session(migrated_schema, session_id, user_id)
    assert abandoned is not None
    assert abandoned.status == SessionStatus.INCOMPLETE
    assert abandoned.transcript[0]["role"] == "assistant"
    assert _checkpoint_count(migrated_schema, session_id) == 0
