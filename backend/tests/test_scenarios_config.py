import pytest

from scenarios.config import get_scenario
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
