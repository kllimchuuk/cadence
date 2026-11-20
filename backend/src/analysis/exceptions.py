from core.exceptions import NotFoundError


class SessionAnalysisNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="session_analysis_not_found",
            message="This session has no analysis yet.",
        )
