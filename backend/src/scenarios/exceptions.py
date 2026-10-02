from core.exceptions import ValidationError


class UnknownScenarioError(ValidationError):
    def __init__(self, scenario_id: str) -> None:
        super().__init__(
            code="unknown_scenario",
            message=f"'{scenario_id}' is not a known scenario.",
            payload={"scenario_id": scenario_id},
        )
