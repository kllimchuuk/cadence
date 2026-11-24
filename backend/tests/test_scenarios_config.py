import pytest

from grammar.reference import load_grammar_skill_keys
from scenarios.config import get_scenario, list_scenarios
from scenarios.exceptions import UnknownScenarioError


@pytest.mark.parametrize(
    "scenario_id",
    [
        "job_interview",
        "daily_standup",
        "client_call",
        "small_talk_networking",
        "presentation_qa",
        "phone_booking",
    ],
)
def test_every_fixed_v1_scenario_is_registered(scenario_id: str) -> None:
    scenario = get_scenario(scenario_id)

    assert scenario.id == scenario_id
    assert scenario.role
    assert scenario.persona
    assert scenario.goal_checklist
    assert scenario.difficulty


def test_an_unknown_scenario_id_is_rejected() -> None:
    with pytest.raises(UnknownScenarioError):
        get_scenario("not_a_real_scenario")


def test_scenarios_are_listed_in_their_defined_order() -> None:
    assert [scenario.id for scenario in list_scenarios()] == [
        "job_interview",
        "daily_standup",
        "client_call",
        "small_talk_networking",
        "presentation_qa",
        "phone_booking",
    ]


def test_every_trained_skill_is_a_key_of_the_grammar_reference() -> None:
    known = set(load_grammar_skill_keys())

    for scenario in list_scenarios():
        assert scenario.trains_skills
        assert set(scenario.trains_skills) <= known


def test_every_grammar_skill_is_trained_by_at_least_one_scenario() -> None:
    trained = {
        skill_key
        for scenario in list_scenarios()
        for skill_key in scenario.trains_skills
    }

    assert trained == set(load_grammar_skill_keys())
