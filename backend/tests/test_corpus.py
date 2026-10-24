from pathlib import Path

import pytest

from rag.corpus import (
    GRAMMAR_REFERENCE_FILE,
    SCENARIO_CONTENT_FILE,
    load_corpus,
)
from rag.exceptions import CorpusFileError
from rag.models import Corpus
from scenarios.exceptions import UnknownScenarioError

SCENARIO_IDS = {
    "job_interview",
    "daily_standup",
    "client_call",
    "small_talk_networking",
    "presentation_qa",
    "phone_booking",
}

VALID_SCENARIO_FILE = "job_interview:\n  - title: Opening\n    content: Hello.\n"
VALID_GRAMMAR_FILE = "- skill_key: articles\n  title: Articles\n  content: Use a.\n"


def _write_corpus(
    directory: Path,
    scenario_file: str = VALID_SCENARIO_FILE,
    grammar_file: str = VALID_GRAMMAR_FILE,
) -> Path:
    (directory / SCENARIO_CONTENT_FILE).write_text(scenario_file)
    (directory / GRAMMAR_REFERENCE_FILE).write_text(grammar_file)
    return directory


def test_the_shipped_corpus_covers_every_scenario_and_has_grammar_rules() -> None:
    entries = load_corpus()

    scenario_entries = [e for e in entries if e.corpus == Corpus.SCENARIO_CONTENT]
    grammar_entries = [e for e in entries if e.corpus == Corpus.GRAMMAR_REFERENCE]
    assert {e.scenario_id for e in scenario_entries} == SCENARIO_IDS
    assert grammar_entries
    assert all(e.skill_key for e in grammar_entries)
    assert all(e.scenario_id is None for e in grammar_entries)
    assert all(e.skill_key is None for e in scenario_entries)


def test_no_two_entries_of_the_shipped_corpus_are_identical() -> None:
    entries = load_corpus()

    assert len({e.content_hash for e in entries}) == len(entries)


def test_a_valid_corpus_directory_is_loaded(tmp_path: Path) -> None:
    entries = load_corpus(_write_corpus(tmp_path))

    assert [(e.corpus, e.scenario_id, e.skill_key) for e in entries] == [
        (Corpus.SCENARIO_CONTENT, "job_interview", None),
        (Corpus.GRAMMAR_REFERENCE, None, "articles"),
    ]


def test_a_scenario_id_that_does_not_exist_is_rejected(tmp_path: Path) -> None:
    directory = _write_corpus(
        tmp_path, scenario_file="no_such_scenario:\n  - title: A\n    content: B\n"
    )

    with pytest.raises(UnknownScenarioError):
        load_corpus(directory)


def test_a_duplicate_skill_key_is_rejected(tmp_path: Path) -> None:
    directory = _write_corpus(tmp_path, grammar_file=VALID_GRAMMAR_FILE * 2)

    with pytest.raises(CorpusFileError, match="unique"):
        load_corpus(directory)


@pytest.mark.parametrize(
    "grammar_file",
    [
        "- skill_key: articles\n  title: Articles\n",
        "- skill_key: articles\n  title: ''\n  content: Use a.\n",
        "- skill_key: articles\n  title: A\n  content: B\n  extra: C\n",
        "not: a list\n",
    ],
)
def test_a_malformed_entry_is_rejected(tmp_path: Path, grammar_file: str) -> None:
    directory = _write_corpus(tmp_path, grammar_file=grammar_file)

    with pytest.raises(CorpusFileError):
        load_corpus(directory)


def test_a_missing_file_is_reported_as_a_corpus_error(tmp_path: Path) -> None:
    with pytest.raises(CorpusFileError):
        load_corpus(tmp_path)
