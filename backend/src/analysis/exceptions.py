from core.exceptions import ValidationError


class InvalidFocusPointCountError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_focus_point_count",
            message="A session analysis must report between 1 and 3 focus points.",
        )
