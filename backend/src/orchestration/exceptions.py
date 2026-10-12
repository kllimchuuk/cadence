from core.exceptions import AppException


class SessionAnalysisFailedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            code="session_analysis_failed",
            message="The post-session analysis could not be completed.",
        )
