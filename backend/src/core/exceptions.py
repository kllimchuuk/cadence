from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR


class AppException(Exception):
    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        code: str,
        message: str,
        payload: dict[str, object] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload or {}
