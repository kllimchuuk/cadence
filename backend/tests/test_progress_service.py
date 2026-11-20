import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.exceptions import SessionAnalysisNotFoundError
from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import GoalOutcome, LanguageFinding, TaskCompletion
from practice.exceptions import LearningSessionNotFoundError
from practice.models import SessionStatus
from practice.repository import LearningSessionRepositoryImpl
from progress.repository import SessionProgressRepositoryImpl
from progress.service import ProgressService
from tests.fakes import analysis_result
from users.repository import UserRepositoryImpl

TRANSCRIPT = [
    {"role": "assistant", "content": "Tell me about yourself."},
    {"role": "user", "content": "I am a backend developer."},
]
GRAMMAR_FINDING = LanguageFinding(
    evidence="I am a backend developer.", issue="none", correction="none"
)
GREETING_GOAL = GoalOutcome(
    goal="greet the candidate", achieved=True, evidence="I am a backend developer."
)


@pytest.fixture
def service(session: AsyncSession) -> ProgressService:
    return ProgressService(
        SessionProgressRepositoryImpl(session),
        SessionAnalysisRepositoryImpl(session),
        LearningSessionRepositoryImpl(session),
    )


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="learner@cadence.test",
        first_name="Learner",
        last_name="One",
        nickname="learner",
        hashed_password="hashed",
    )
    return user.id


@pytest_asyncio.fixture
async def other_user_id(session: AsyncSession) -> uuid.UUID:
    user = await UserRepositoryImpl(session).create(
        email="other@cadence.test",
        first_name="Other",
        last_name="Learner",
        nickname="other-learner",
        hashed_password="hashed",
    )
    return user.id


async def _analysed_session_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    sessions = LearningSessionRepositoryImpl(session)
    record = await sessions.create(user_id, "job_interview")
    await sessions.finish(record, SessionStatus.COMPLETED, TRANSCRIPT, None)
    analysis = analysis_result().model_copy(
        update={
            "grammar_findings": [GRAMMAR_FINDING],
            "task_completion": TaskCompletion(goals=[GREETING_GOAL]),
        }
    )
    await SessionAnalysisRepositoryImpl(session).create(record.id, user_id, analysis)
    return record.id


@pytest.mark.asyncio
async def test_recording_a_session_stores_its_measured_progress(
    session: AsyncSession, service: ProgressService, user_id: uuid.UUID
) -> None:
    session_id = await _analysed_session_id(session, user_id)

    progress = await service.record_session(session_id, user_id)

    assert progress.session_id == session_id
    assert progress.grammar_issue_count == 1
    assert progress.goals_achieved == 1
    assert progress.goals_total == 4
    assert progress.learner_word_count == 5
    assert progress.total_word_count == 9


@pytest.mark.asyncio
async def test_recording_a_session_twice_is_a_no_op(
    session: AsyncSession, service: ProgressService, user_id: uuid.UUID
) -> None:
    session_id = await _analysed_session_id(session, user_id)

    first = await service.record_session(session_id, user_id)
    second = await service.record_session(session_id, user_id)

    assert second.id == first.id


@pytest.mark.asyncio
async def test_recording_an_unknown_session_raises_not_found(
    service: ProgressService, user_id: uuid.UUID
) -> None:
    with pytest.raises(LearningSessionNotFoundError):
        await service.record_session(uuid.uuid4(), user_id)


@pytest.mark.asyncio
async def test_recording_another_users_session_raises_not_found(
    session: AsyncSession,
    service: ProgressService,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    session_id = await _analysed_session_id(session, user_id)

    with pytest.raises(LearningSessionNotFoundError):
        await service.record_session(session_id, other_user_id)


@pytest.mark.asyncio
async def test_recording_a_session_without_an_analysis_raises_not_found(
    session: AsyncSession, service: ProgressService, user_id: uuid.UUID
) -> None:
    record = await LearningSessionRepositoryImpl(session).create(
        user_id, "job_interview"
    )

    with pytest.raises(SessionAnalysisNotFoundError):
        await service.record_session(record.id, user_id)


@pytest.mark.asyncio
async def test_the_report_holds_the_users_sessions_and_their_trend(
    session: AsyncSession,
    service: ProgressService,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    for _ in range(2):
        await service.record_session(
            await _analysed_session_id(session, user_id), user_id
        )
    await service.record_session(
        await _analysed_session_id(session, other_user_id), other_user_id
    )

    report = await service.get_report(user_id)

    assert len(report.sessions) == 2
    assert report.trend.grammar_issue_rate is not None
