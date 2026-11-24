import uuid
from datetime import UTC, datetime

from scenarios.recommendation import recommend_scenario
from weaknesses.models import WeaknessCategory, WeaknessRecord, WeaknessState


def _weakness(skill_key: str) -> WeaknessRecord:
    return WeaknessRecord(
        user_id=uuid.uuid4(),
        category=WeaknessCategory.GRAMMAR,
        skill_key=skill_key,
        state=WeaknessState.ACTIVE,
    )


def test_nothing_is_recommended_without_active_weaknesses() -> None:
    assert recommend_scenario([], {}) is None


def test_the_scenario_training_the_most_active_weaknesses_wins() -> None:
    weaknesses = [
        _weakness("conditionals"),
        _weakness("reported_speech"),
        _weakness("relative_clauses"),
    ]

    match = recommend_scenario(weaknesses, {})

    assert match is not None
    assert match.scenario.id == "presentation_qa"
    assert {weakness.skill_key for weakness in match.weaknesses} == {
        "conditionals",
        "reported_speech",
        "relative_clauses",
    }


def test_a_tie_goes_to_the_scenario_practised_least_recently() -> None:
    weaknesses = [_weakness("question_word_order")]
    last_completed = {
        "job_interview": datetime(2026, 11, 10, tzinfo=UTC),
        "small_talk_networking": datetime(2026, 11, 1, tzinfo=UTC),
        "phone_booking": datetime(2026, 11, 5, tzinfo=UTC),
    }

    match = recommend_scenario(weaknesses, last_completed)

    assert match is not None
    assert match.scenario.id == "small_talk_networking"


def test_a_tie_prefers_a_scenario_never_completed() -> None:
    weaknesses = [_weakness("question_word_order")]
    last_completed = {
        "job_interview": datetime(2026, 11, 10, tzinfo=UTC),
        "small_talk_networking": datetime(2026, 11, 1, tzinfo=UTC),
    }

    match = recommend_scenario(weaknesses, last_completed)

    assert match is not None
    assert match.scenario.id == "phone_booking"


def test_a_skill_every_conversation_trains_ties_across_all_scenarios() -> None:
    last_completed = {
        scenario_id: datetime(2026, 11, 1, tzinfo=UTC)
        for scenario_id in (
            "job_interview",
            "daily_standup",
            "client_call",
            "small_talk_networking",
            "presentation_qa",
        )
    }

    match = recommend_scenario([_weakness("articles")], last_completed)

    assert match is not None
    assert match.scenario.id == "phone_booking"
