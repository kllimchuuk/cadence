from core.exceptions import AppException


class CorpusFileError(AppException):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            code="corpus_file_error",
            message=f"Invalid corpus file {path}: {reason}",
            payload={"path": path},
        )
