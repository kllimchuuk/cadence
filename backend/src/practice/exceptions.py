from core.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    ValidationError,
)


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


class TooManyActiveSessionsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            code="too_many_active_sessions",
            message="Finish an ongoing practice session before starting another.",
        )


class PracticeSessionIdleError(AppException):
    def __init__(self) -> None:
        super().__init__(
            code="practice_session_idle",
            message="No message arrived before the idle timeout.",
        )
