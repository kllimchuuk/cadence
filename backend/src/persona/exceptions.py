from core.exceptions import ValidationError


class InvalidFactError(ValidationError):
    def __init__(self) -> None:
        super().__init__(code="invalid_fact", message="A fact must not be blank.")
