from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter

from core.content_file import CONTENT_DIR, read_content_file
from grammar.reference import load_grammar_rules
from rag.entries import ContentEntry
from rag.models import Corpus
from scenarios.config import get_scenario

SCENARIO_CONTENT_FILE = "scenario_content.yaml"


class _ScenarioEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_min_length=1)

    title: str
    content: str


_SCENARIO_FILE = TypeAdapter(dict[str, list[_ScenarioEntry]])


def _load_scenario_content(path: Path) -> list[ContentEntry]:
    scenarios = read_content_file(path, _SCENARIO_FILE)
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


def _load_grammar_reference(directory: Path) -> list[ContentEntry]:
    return [
        ContentEntry(
            corpus=Corpus.GRAMMAR_REFERENCE,
            skill_key=rule.skill_key,
            title=rule.title,
            content=rule.content,
        )
        for rule in load_grammar_rules(directory)
    ]


def load_corpus(directory: Path = CONTENT_DIR) -> list[ContentEntry]:
    return _load_scenario_content(
        directory / SCENARIO_CONTENT_FILE
    ) + _load_grammar_reference(directory)
