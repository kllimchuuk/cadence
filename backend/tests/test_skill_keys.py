from rag.corpus import load_corpus
from rag.models import Corpus
from weaknesses.skill_keys import GrammarSkillKey


def test_the_vocabulary_is_exactly_the_grammar_corpus_keys() -> None:
    corpus_keys = {
        entry.skill_key
        for entry in load_corpus()
        if entry.corpus == Corpus.GRAMMAR_REFERENCE
    }

    assert {key.value for key in GrammarSkillKey} == corpus_keys
