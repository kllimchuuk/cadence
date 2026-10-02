from core.exceptions import AppException


class LLMResponseError(AppException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            code="llm_response_error",
            message=f"The LLM provider returned no usable response: {reason}",
        )
