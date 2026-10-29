from enum import StrEnum

from grammar.reference import load_grammar_skill_keys
from weaknesses.exceptions import InvalidSkillKeyError
from weaknesses.models import WeaknessCategory

GrammarSkillKey = StrEnum(
    "GrammarSkillKey", {key: key for key in load_grammar_skill_keys()}
)

SKILL_VOCABULARY: dict[WeaknessCategory, frozenset[str]] = {
    WeaknessCategory.GRAMMAR: frozenset(key.value for key in GrammarSkillKey),
}


def category_of(skill_key: str) -> WeaknessCategory:
    for category, skill_keys in SKILL_VOCABULARY.items():
        if skill_key in skill_keys:
            return category
    raise InvalidSkillKeyError()
