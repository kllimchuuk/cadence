import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orchestration.analysis_runner import SessionAnalysisRunner
from orchestration.context import AnalysisRuntimeContext
from orchestration.exceptions import SessionAnalysisFailedError
from orchestration.graph import build_analysis_graph
from practice.models import AnalysisStatus, LearningSession, SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from practice.service import PracticeService
from users.repository import UserRepositoryImpl

from tests.fakes import FailingAnalysisLLMClient, FakeEmbeddingClient, FakeLLMClient

TRANSCRIPT = [
    {"role": "assistant", "content": "Hi, thanks for joining!"},
    {"role": "user", "content": "Yesterday I go to the office."},
    {"role": "assistant", "content": "Thanks for practising today."},
]


@pytest.fixture
def practice_service(session: AsyncSession) -> PracticeService:
    return PracticeService(LearningSessionRepositoryImpl(session))


@pytest_asyncio.fixture
async def completed_session(
    session: AsyncSession, practice_service: PracticeService
) -> LearningSession:
    user = await UserRepositoryImpl(session).create(
        email="learner@cadence.test",
        first_name="Learner",
        last_name="One",
        nickname="learner",
        hashed_password="hashed",
    )
    started = await practice_service.start_session(user.id, "job_interview")
    return await practice_service.finish_session(
        started.id, user.id, SessionStatus.COMPLETED, TRANSCRIPT
    )


def _runner(
    session_factory: async_sessionmaker[AsyncSession],
    session_analysis_llm: FakeLLMClient,
) -> SessionAnalysisRunner:
    return SessionAnalysisRunner(
        session_factory,
        AnalysisRuntimeContext(
            session_analysis_llm=session_analysis_llm,
            embedder=FakeEmbeddingClient(),
            session_factory=session_factory,
        ),
        build_analysis_graph(),
    )


async def _reloaded(
    session: AsyncSession,
    practice_service: PracticeService,
    learning_session: LearningSession,
) -> LearningSession:
    session_id, user_id = learning_session.id, learning_session.user_id
    session.expire_all()
    return await practice_service.get_session(session_id, user_id)


@pytest.mark.asyncio
async def test_a_successful_analysis_returns_its_focus_points_and_completes(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    practice_service: PracticeService,
    completed_session: LearningSession,
) -> None:
    session_analysis_llm = FakeLLMClient()

    focus_points = await _runner(session_factory, session_analysis_llm).analyse(
        completed_session
    )

    assert focus_points == ("Practice past-tense verbs",)
    reloaded = await _reloaded(session, practice_service, completed_session)
    assert reloaded.analysis_status == AnalysisStatus.COMPLETED


@pytest.mark.asyncio
async def test_the_analysis_reads_the_transcript_stored_for_the_session(
    session_factory: async_sessionmaker[AsyncSession],
    completed_session: LearningSession,
) -> None:
    session_analysis_llm = FakeLLMClient()
    stale_handle = LearningSession(
        id=completed_session.id,
        user_id=completed_session.user_id,
        scenario_id=completed_session.scenario_id,
    )

    await _runner(session_factory, session_analysis_llm).analyse(stale_handle)

    (message,) = session_analysis_llm.requests[0].messages
    assert json.loads(message.content) == TRANSCRIPT


@pytest.mark.asyncio
async def test_a_failed_analysis_is_recorded_and_reported(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    practice_service: PracticeService,
    completed_session: LearningSession,
) -> None:
    runner = _runner(session_factory, FailingAnalysisLLMClient())

    with pytest.raises(SessionAnalysisFailedError):
        await runner.analyse(completed_session)

    reloaded = await _reloaded(session, practice_service, completed_session)
    assert reloaded.analysis_status == AnalysisStatus.FAILED


@pytest.mark.asyncio
async def test_a_failed_analysis_leaves_the_conversation_completed(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    practice_service: PracticeService,
    completed_session: LearningSession,
) -> None:
    runner = _runner(session_factory, FailingAnalysisLLMClient())

    with pytest.raises(SessionAnalysisFailedError):
        await runner.analyse(completed_session)

    reloaded = await _reloaded(session, practice_service, completed_session)
    assert reloaded.status == SessionStatus.COMPLETED


async def _unrecordable_status(*args: object) -> None:
    raise ConnectionError("database unavailable")


@pytest.mark.asyncio
async def test_an_unrecordable_status_does_not_hide_a_successful_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    completed_session: LearningSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PracticeService, "record_analysis_status", _unrecordable_status)

    focus_points = await _runner(session_factory, FakeLLMClient()).analyse(
        completed_session
    )

    assert focus_points == ("Practice past-tense verbs",)


@pytest.mark.asyncio
async def test_an_unrecordable_status_still_reports_a_failed_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    completed_session: LearningSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PracticeService, "record_analysis_status", _unrecordable_status)
    runner = _runner(session_factory, FailingAnalysisLLMClient())

    with pytest.raises(SessionAnalysisFailedError):
        await runner.analyse(completed_session)
