from core.exceptions import AppException


class PracticeSessionIdleError(AppException):
    def __init__(self) -> None:
        super().__init__(
            code="practice_session_idle",
            message="No message arrived before the idle timeout.",
        )
