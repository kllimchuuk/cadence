import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.repository import SessionAnalysisRepositoryImpl
from analysis.schemas import SkillObservation
from practice.repository import LearningSessionRepositoryImpl
from scenarios.service import ScenarioRecommendationService
from tests.fakes import analysis_result
from users.repository import UserRepositoryImpl
from weaknesses.models import WeaknessCategory
from weaknesses.repository import WeaknessRecordRepositoryImpl

SKILL_KEY = "question_word_order"


@pytest.fixture
def service(session: AsyncSession) -> ScenarioRecommendationService:
    return ScenarioRecommendationService(
        WeaknessRecordRepositoryImpl(session),
        LearningSessionRepositoryImpl(session),
        SessionAnalysisRepositoryImpl(session),
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


async def _track_weakness(session: AsyncSession, user_id: uuid.UUID) -> None:
    await WeaknessRecordRepositoryImpl(session).create(
        user_id, WeaknessCategory.GRAMMAR, SKILL_KEY
    )


async def _store_analysis(
    session: AsyncSession,
    user_id: uuid.UUID,
    evidence: str,
    outcome: str = "error",
    created_at: datetime | None = None,
) -> None:
    record = await LearningSessionRepositoryImpl(session).create(
        user_id, "job_interview"
    )
    observation = SkillObservation(
        skill_key=SKILL_KEY, outcome=outcome, evidence=evidence, note="note"
    )
    analysis = await SessionAnalysisRepositoryImpl(session).create(
        record.id, user_id, analysis_result(skill_observations=[observation])
    )
    if created_at is not None:
        analysis.created_at = created_at
        await session.flush()


@pytest.mark.asyncio
async def test_nothing_is_recommended_without_active_weaknesses(
    service: ScenarioRecommendationService, user_id: uuid.UUID
) -> None:
    assert await service.recommend(user_id) is None


@pytest.mark.asyncio
async def test_the_reason_quotes_what_the_learner_really_said(
    session: AsyncSession, service: ScenarioRecommendationService, user_id: uuid.UUID
) -> None:
    await _track_weakness(session, user_id)
    await _store_analysis(session, user_id, "Where you live now?")

    recommendation = await service.recommend(user_id)

    assert recommendation is not None
    assert SKILL_KEY in recommendation.scenario.trains_skills
    (reason,) = recommendation.reasons
    assert reason.skill_key == SKILL_KEY
    assert reason.state == "active"
    assert reason.evidence == "Where you live now?"


@pytest.mark.asyncio
async def test_the_newest_error_quote_is_the_one_reported(
    session: AsyncSession, service: ScenarioRecommendationService, user_id: uuid.UUID
) -> None:
    await _track_weakness(session, user_id)
    await _store_analysis(
        session,
        user_id,
        "Old mistake here.",
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    await _store_analysis(
        session,
        user_id,
        "Fresh mistake here.",
        created_at=datetime(2026, 11, 9, tzinfo=UTC),
    )

    recommendation = await service.recommend(user_id)

    assert recommendation is not None
    assert recommendation.reasons[0].evidence == "Fresh mistake here."


@pytest.mark.asyncio
async def test_a_clean_use_is_never_reported_as_the_evidence_of_an_error(
    session: AsyncSession, service: ScenarioRecommendationService, user_id: uuid.UUID
) -> None:
    await _track_weakness(session, user_id)
    await _store_analysis(session, user_id, "Where do you live?", outcome="clean")

    recommendation = await service.recommend(user_id)

    assert recommendation is not None
    assert recommendation.reasons[0].evidence is None


@pytest.mark.asyncio
async def test_another_users_weaknesses_are_not_used(
    session: AsyncSession,
    service: ScenarioRecommendationService,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    await _track_weakness(session, other_user_id)
    await _store_analysis(session, other_user_id, "Where you live now?")

    assert await service.recommend(user_id) is None
