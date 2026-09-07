from core.exceptions import AppException


class EmailAlreadyRegisteredError(AppException):
    status_code = 409

    def __init__(self) -> None:
        super().__init__(
            code="email_already_registered",
            message="This email is already registered.",
        )


class InvalidCredentialsError(AppException):
    status_code = 401

    def __init__(self) -> None:
        super().__init__(
            code="invalid_credentials", message="Invalid email or password."
        )


class NotAuthenticatedError(AppException):
    status_code = 401

    def __init__(self) -> None:
        super().__init__(code="not_authenticated", message="Authentication required.")
