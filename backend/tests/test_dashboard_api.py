import asyncio
import uuid
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import LanguageFinding, SkillObservation
from config import Settings
from core.database import build_engine
from main import create_app
from practice.models import AnalysisStatus, LearningSession, SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from progress.repository import SessionProgressRepositoryImpl
from progress.service import ProgressService
from tests.fakes import analysis_result
from tests.helpers import settings_kwargs
from tests.test_auth_api import register_payload
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory, WeaknessState
from weaknesses.repository import WeaknessRecordRepositoryImpl

T = TypeVar("T")

TRANSCRIPT = [
    {"role": "assistant", "content": "Tell me about yourself."},
    {"role": "user", "content": "I am a backend developer."},
]
GRAMMAR_FINDING = LanguageFinding(
    evidence="I am a backend developer.", issue="none", correction="none"
)
FIRST_DAY = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
def app_database_url(migrated_schema: str) -> str:
    return migrated_schema


@pytest.fixture
def client(app_database_url: str) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, **settings_kwargs(DATABASE_URL=app_database_url)
    )

    with TestClient(create_app(settings), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def user_id(client: TestClient) -> uuid.UUID:
    client.post("/auth/register", json=register_payload())
    return uuid.UUID(client.get("/auth/me").json()["id"])


def seed(app_database_url: str, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        engine = build_engine(app_database_url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                result = await work(session)
                await session.commit()
                return result
        finally:
            await engine.dispose()

    return asyncio.run(run())


async def _create_other_user(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email=f"{uuid.uuid4()}@cadence.example",
        first_name="Other",
        last_name="Learner",
        nickname=f"other{uuid.uuid4().hex[:12]}",
        hashed_password="hashed",
    )
    return user.id


async def _completed_session(
    session: AsyncSession,
    user_id: uuid.UUID,
    scenario_id: str = "job_interview",
    day: int = 0,
) -> LearningSession:
    repository = LearningSessionRepositoryImpl(session)
    record = await repository.create(user_id, scenario_id)
    await repository.finish(
        record, SessionStatus.COMPLETED, TRANSCRIPT, AnalysisStatus.COMPLETED
    )
    record.started_at = FIRST_DAY + timedelta(days=day)
    record.ended_at = FIRST_DAY + timedelta(days=day, hours=1)
    await session.flush()
    return record


async def _analyse_and_measure(
    session: AsyncSession,
    user_id: uuid.UUID,
    learning_session: LearningSession,
    grammar_findings: int = 0,
    skill_observations: list[SkillObservation] | None = None,
) -> None:
    result = analysis_result(skill_observations=skill_observations).model_copy(
        update={"grammar_findings": [GRAMMAR_FINDING] * grammar_findings}
    )
    analyses = SessionAnalysisRepositoryImpl(session)
    await analyses.create(learning_session.id, user_id, result)
    await ProgressService(
        SessionProgressRepositoryImpl(session),
        analyses,
        LearningSessionRepositoryImpl(session),
    ).record_session(learning_session.id, user_id)


@pytest.mark.parametrize(
    "path",
    [
        "/scenarios",
        "/scenarios/recommendation",
        "/sessions",
        f"/sessions/{uuid.uuid4()}",
        "/weaknesses",
        "/progress",
    ],
)
def test_every_dashboard_endpoint_requires_a_signed_in_user(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_scenarios_are_listed_with_their_goal_checklists(
    client: TestClient, user_id: uuid.UUID
) -> None:
    response = client.get("/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert [scenario["id"] for scenario in scenarios] == [
        "job_interview",
        "daily_standup",
        "client_call",
        "small_talk_networking",
        "presentation_qa",
        "phone_booking",
    ]
    assert all(scenario["goal_checklist"] for scenario in scenarios)
    assert all("trains_skills" not in scenario for scenario in scenarios)


def test_sessions_come_back_newest_first_and_are_paged(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> None:
        for day, scenario_id in enumerate(
            ("job_interview", "daily_standup", "client_call")
        ):
            await _completed_session(session, user_id, scenario_id, day)

    seed(app_database_url, work)

    everything = client.get("/sessions").json()
    middle = client.get("/sessions", params={"limit": 1, "offset": 1}).json()

    assert [item["scenario_id"] for item in everything] == [
        "client_call",
        "daily_standup",
        "job_interview",
    ]
    assert [item["scenario_id"] for item in middle] == ["daily_standup"]
    assert "transcript" not in everything[0]


def test_only_the_users_own_sessions_are_listed(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> None:
        await _completed_session(session, user_id)
        other_user_id = await _create_other_user(session)
        await _completed_session(session, other_user_id, "client_call")

    seed(app_database_url, work)

    listed = client.get("/sessions").json()

    assert [item["scenario_id"] for item in listed] == ["job_interview"]


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}], ids=str
)
def test_the_page_window_is_bounded(
    client: TestClient, user_id: uuid.UUID, params: dict[str, int]
) -> None:
    assert client.get("/sessions", params=params).status_code == 422


def test_a_session_comes_back_with_its_transcript_and_analysis(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> uuid.UUID:
        record = await _completed_session(session, user_id)
        await _analyse_and_measure(session, user_id, record, grammar_findings=1)
        return record.id

    session_id = seed(app_database_url, work)

    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["id"] == str(session_id)
    assert body["session"]["status"] == "completed"
    assert body["session"]["transcript"] == TRANSCRIPT
    assert body["analysis"]["grammar_findings"] == [GRAMMAR_FINDING.model_dump()]
    assert body["analysis"]["focus_points"] == [
        {
            "text": "Practice past-tense verbs",
            "evidence": "Yesterday I go to the office.",
        }
    ]
    assert body["analysis"]["task_completion"] == {"goals": []}


def test_a_session_without_an_analysis_has_none(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> uuid.UUID:
        record = await LearningSessionRepositoryImpl(session).create(
            user_id, "job_interview"
        )
        return record.id

    session_id = seed(app_database_url, work)

    body = client.get(f"/sessions/{session_id}").json()

    assert body["session"]["status"] == "in_progress"
    assert body["session"]["transcript"] is None
    assert body["analysis"] is None


def test_an_unknown_session_is_not_found(
    client: TestClient, user_id: uuid.UUID
) -> None:
    response = client.get(f"/sessions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "learning_session_not_found"


def test_another_users_session_is_not_found(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> uuid.UUID:
        other_user_id = await _create_other_user(session)
        return (await _completed_session(session, other_user_id)).id

    other_session_id = seed(app_database_url, work)

    response = client.get(f"/sessions/{other_session_id}")

    assert response.status_code == 404
    assert response.json()["code"] == "learning_session_not_found"


def test_weaknesses_include_mastered_ones_but_only_the_users_own(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> None:
        weaknesses = WeaknessRecordRepositoryImpl(session)
        mastered = await weaknesses.create(
            user_id, WeaknessCategory.GRAMMAR, "articles"
        )
        await weaknesses.update_state(mastered, WeaknessState.MASTERED, 0, None)
        await weaknesses.create(user_id, WeaknessCategory.GRAMMAR, "conditionals")
        other_user_id = await _create_other_user(session)
        await weaknesses.create(other_user_id, WeaknessCategory.GRAMMAR, "modal_verbs")

    seed(app_database_url, work)

    listed = client.get("/weaknesses").json()

    assert {item["skill_key"]: item["state"] for item in listed} == {
        "articles": "mastered",
        "conditionals": "active",
    }


def test_progress_is_empty_for_a_new_learner(
    client: TestClient, user_id: uuid.UUID
) -> None:
    body = client.get("/progress").json()

    assert body["sessions"] == []
    assert body["trend"] == {
        "grammar_issue_rate": None,
        "vocabulary_issue_rate": None,
        "goal_completion_rate": None,
        "learner_word_share": None,
    }


def test_progress_lists_sessions_oldest_first_with_a_trend(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    for day, grammar_findings in ((0, 4), (1, 0)):

        async def work(
            session: AsyncSession, day: int = day, findings: int = grammar_findings
        ) -> None:
            record = await _completed_session(session, user_id, day=day)
            await _analyse_and_measure(
                session, user_id, record, grammar_findings=findings
            )

        seed(app_database_url, work)

    body = client.get("/progress").json()

    assert [item["grammar_issue_count"] for item in body["sessions"]] == [4, 0]
    assert body["sessions"][0]["learner_word_count"] == 5
    assert body["sessions"][0]["grammar_issue_rate"] == 80.0
    assert body["trend"]["grammar_issue_rate"] == {
        "baseline": 80.0,
        "latest": 0.0,
        "direction": "improving",
    }


def test_nothing_is_recommended_without_active_weaknesses(
    client: TestClient, user_id: uuid.UUID
) -> None:
    response = client.get("/scenarios/recommendation")

    assert response.status_code == 200
    assert response.json() == {"scenario": None, "reasons": []}


def test_the_recommendation_quotes_what_the_learner_really_said(
    client: TestClient, app_database_url: str, user_id: uuid.UUID
) -> None:
    async def work(session: AsyncSession) -> None:
        await WeaknessRecordRepositoryImpl(session).create(
            user_id, WeaknessCategory.GRAMMAR, "question_word_order"
        )
        record = await _completed_session(session, user_id, "daily_standup")
        observation = SkillObservation(
            skill_key="question_word_order",
            outcome="error",
            evidence="Where you live now?",
            note="Wrong word order in a question.",
        )
        await _analyse_and_measure(
            session, user_id, record, skill_observations=[observation]
        )

    seed(app_database_url, work)

    body = client.get("/scenarios/recommendation").json()

    assert body["scenario"]["id"] in {
        "job_interview",
        "small_talk_networking",
        "phone_booking",
    }
    assert body["reasons"] == [
        {
            "skill_key": "question_word_order",
            "state": "active",
            "evidence": "Where you live now?",
        }
    ]
