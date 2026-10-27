from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter

from core.content_file import CONTENT_DIR, CorpusFileError, read_content_file

GRAMMAR_REFERENCE_FILE = "grammar_reference.yaml"


class GrammarRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_min_length=1, frozen=True)

    skill_key: str
    title: str
    content: str


_GRAMMAR_FILE = TypeAdapter(list[GrammarRule])


def load_grammar_rules(directory: Path = CONTENT_DIR) -> list[GrammarRule]:
    path = directory / GRAMMAR_REFERENCE_FILE
    rules = read_content_file(path, _GRAMMAR_FILE)
    skill_keys = [rule.skill_key for rule in rules]
    if len(set(skill_keys)) != len(skill_keys):
        raise CorpusFileError(path.name, "skill_key values must be unique")
    return rules


def load_grammar_skill_keys(directory: Path = CONTENT_DIR) -> list[str]:
    return [rule.skill_key for rule in load_grammar_rules(directory)]
