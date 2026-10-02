from core.exceptions import NotFoundError, ValidationError


class LearningSessionNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="learning_session_not_found", message="Learning session not found."
        )


class InvalidSessionStatusError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_session_status",
            message="A session can only be finished as completed or incomplete.",
        )
