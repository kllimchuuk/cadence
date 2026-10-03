import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from config import Settings
from core.database import build_engine, build_session_factory
from llm.dependencies import get_llm_client_factory
from main import create_app
from orchestration.nodes import conversing as conversing_node_module
from orchestration.schemas import SessionAnalysisResult
from practice.models import LearningSession, SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.websocket import (
    INVALID_REQUEST_CLOSE_CODE,
    UNAUTHENTICATED_CLOSE_CODE,
)
from tests.helpers import settings_kwargs


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
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/practice/sessions/ws?scenario_id=job_interview"
        ):
            pass

    assert exc_info.value.code == UNAUTHENTICATED_CLOSE_CODE


def test_connecting_with_an_unknown_scenario_is_rejected(client: TestClient) -> None:
    client.post("/auth/register", json=register_payload())

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/practice/sessions/ws?scenario_id=not-a-scenario"
        ):
            pass

    assert exc_info.value.code == INVALID_REQUEST_CLOSE_CODE


def test_a_malformed_frame_closes_the_socket_as_a_bad_request(
    client: TestClient,
) -> None:
    client.post("/auth/register", json=register_payload())

    with client.websocket_connect(
        "/practice/sessions/ws?scenario_id=job_interview"
    ) as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "user_message"})

        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == INVALID_REQUEST_CLOSE_CODE


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
            ws.send_json({"type": "user_message", "content": "Sure, let's continue."})

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


def test_disconnecting_mid_conversation_leaves_the_session_in_progress(
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

    in_progress = _fetch_session(migrated_schema, session_id, user_id)
    assert in_progress is not None
    assert in_progress.status == SessionStatus.IN_PROGRESS
