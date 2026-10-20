from enum import StrEnum

from rag.corpus import load_grammar_skill_keys

GrammarSkillKey = StrEnum(
    "GrammarSkillKey", {key: key for key in load_grammar_skill_keys()}
)
