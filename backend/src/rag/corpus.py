from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from config import BACKEND_DIR
from rag.entries import ContentEntry
from rag.exceptions import CorpusFileError
from rag.models import Corpus
from scenarios.config import get_scenario

CONTENT_DIR = BACKEND_DIR / "content"
SCENARIO_CONTENT_FILE = "scenario_content.yaml"
GRAMMAR_REFERENCE_FILE = "grammar_reference.yaml"


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_min_length=1)

    title: str
    content: str


class _GrammarEntry(_Entry):
    skill_key: str


_SCENARIO_FILE = TypeAdapter(dict[str, list[_Entry]])
_GRAMMAR_FILE = TypeAdapter(list[_GrammarEntry])


def _read(path: Path, adapter: TypeAdapter):
    try:
        return adapter.validate_python(yaml.safe_load(path.read_text()))
    except (OSError, yaml.YAMLError, PydanticValidationError) as error:
        raise CorpusFileError(path.name, str(error)) from error


def _load_scenario_content(path: Path) -> list[ContentEntry]:
    scenarios = _read(path, _SCENARIO_FILE)
    return [
        ContentEntry(
            corpus=Corpus.SCENARIO_CONTENT,
            scenario_id=get_scenario(scenario_id).id,
            title=entry.title,
            content=entry.content,
        )
        for scenario_id, entries in scenarios.items()
        for entry in entries
    ]


def _load_grammar_reference(path: Path) -> list[ContentEntry]:
    entries = _read(path, _GRAMMAR_FILE)
    skill_keys = [entry.skill_key for entry in entries]
    if len(set(skill_keys)) != len(skill_keys):
        raise CorpusFileError(path.name, "skill_key values must be unique")
    return [
        ContentEntry(
            corpus=Corpus.GRAMMAR_REFERENCE,
            skill_key=entry.skill_key,
            title=entry.title,
            content=entry.content,
        )
        for entry in entries
    ]


def load_corpus(directory: Path = CONTENT_DIR) -> list[ContentEntry]:
    return _load_scenario_content(
        directory / SCENARIO_CONTENT_FILE
    ) + _load_grammar_reference(directory / GRAMMAR_REFERENCE_FILE)
