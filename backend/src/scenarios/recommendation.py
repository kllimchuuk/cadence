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


def recommend_scenario(
    weaknesses: Sequence[WeaknessRecord], last_completed: Mapping[str, datetime]
) -> ScenarioMatch | None:
    if not weaknesses:
        return None

    matches = [
        ScenarioMatch(
            scenario,
            tuple(
                weakness
                for weakness in weaknesses
                if weakness.skill_key in scenario.trains_skills
            ),
        )
        for scenario in list_scenarios()
    ]
    return min(
        matches,
        key=lambda match: (
            -len(match.weaknesses),
            last_completed.get(match.scenario.id, _NEVER_PRACTISED),
        ),
    )
