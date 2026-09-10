from core.exceptions import ConflictError, UnauthorizedError


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            code="email_already_registered",
            message="This email is already registered — try logging in instead.",
        )


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_credentials", message="Invalid email or password."
        )


class NotAuthenticatedError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(code="not_authenticated", message="Authentication required.")


class NicknameAlreadyTakenError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            code="nickname_already_taken",
            message="This nickname is already taken — try another one.",
        )


class GoogleAuthenticationError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(
            code="google_authentication_failed",
            message="Google sign-in failed. Please try again.",
        )
