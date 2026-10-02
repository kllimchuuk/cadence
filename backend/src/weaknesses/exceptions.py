from core.exceptions import ValidationError


class InvalidSkillKeyError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_skill_key", message="skill_key must not be blank."
        )
