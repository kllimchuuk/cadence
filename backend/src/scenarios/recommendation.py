from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from scenarios.config import Scenario, list_scenarios
from weaknesses.models import WeaknessRecord

_NEVER_PRACTISED = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class ScenarioMatch:
    scenario: Scenario
    weaknesses: tuple[WeaknessRecord, ...]


def _match(scenario: Scenario, weaknesses: Sequence[WeaknessRecord]) -> ScenarioMatch:
    trained = tuple(
        weakness
        for weakness in weaknesses
        if weakness.skill_key in scenario.trains_skills
    )
    return ScenarioMatch(scenario, trained)


def _priority(
    match: ScenarioMatch, last_completed: Mapping[str, datetime]
) -> tuple[int, datetime]:
    return (
        -len(match.weaknesses),
        last_completed.get(match.scenario.id, _NEVER_PRACTISED),
    )


def recommend_scenario(
    weaknesses: Sequence[WeaknessRecord], last_completed: Mapping[str, datetime]
) -> ScenarioMatch | None:
    if not weaknesses:
        return None

    matches = [_match(scenario, weaknesses) for scenario in list_scenarios()]
    return min(matches, key=lambda match: _priority(match, last_completed))
