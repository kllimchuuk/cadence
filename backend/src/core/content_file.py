from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from config import BACKEND_DIR
from core.exceptions import AppException

ParsedT = TypeVar("ParsedT")

CONTENT_DIR = BACKEND_DIR / "content"


class CorpusFileError(AppException):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            code="corpus_file_error",
            message=f"Invalid corpus file {path}: {reason}",
            payload={"path": path},
        )


def read_content_file(path: Path, adapter: TypeAdapter[ParsedT]) -> ParsedT:
    try:
        return adapter.validate_python(yaml.safe_load(path.read_text()))
    except (OSError, yaml.YAMLError, PydanticValidationError) as error:
        raise CorpusFileError(path.name, str(error)) from error
