from analysis.evidence import find_unquoted_evidence, keep_quoted, learner_turns
from analysis.schemas import PersonaFact, SkillObservation
from tests.fakes import analysis_result

TRANSCRIPT = [
    {"role": "assistant", "content": "Where do you work now?"},
    {"role": "user", "content": "I work at a small company, in Kyiv."},
    {"role": "user", "content": "Yesterday I go to the office."},
]


def _observation(evidence: str) -> SkillObservation:
    return SkillObservation(
        skill_key="articles", outcome="error", evidence=evidence, note="n"
    )


def test_a_quote_ignores_case_punctuation_and_spacing() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(
        skill_observations=[_observation("  YESTERDAY, i go   to the office ")]
    )

    assert find_unquoted_evidence(result, turns) == []


def test_a_quote_may_be_a_part_of_a_turn() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(skill_observations=[_observation("a small company")])

    assert find_unquoted_evidence(result, turns) == []


def test_words_only_the_assistant_said_are_not_evidence() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(skill_observations=[_observation("Where do you work")])

    assert find_unquoted_evidence(result, turns) == ["Where do you work"]


def test_a_quote_cannot_span_two_turns() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(
        skill_observations=[_observation("in Kyiv Yesterday I go")]
    )

    assert find_unquoted_evidence(result, turns) == ["in Kyiv Yesterday I go"]


def test_a_quote_must_match_whole_words() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(skill_observations=[_observation("I wor")])

    assert find_unquoted_evidence(result, turns) == ["I wor"]


def test_an_empty_quote_is_never_evidence() -> None:
    turns = learner_turns(TRANSCRIPT)
    result = analysis_result(skill_observations=[_observation("...")])

    assert find_unquoted_evidence(result, turns) == ["..."]


def test_facts_are_checked_and_unquoted_items_are_dropped() -> None:
    turns = learner_turns(TRANSCRIPT)
    kept = PersonaFact(fact="Works in Kyiv.", evidence="a small company, in Kyiv")
    invented = PersonaFact(fact="Has a dog.", evidence="I have a dog")
    result = analysis_result(
        skill_observations=[_observation("Yesterday I go"), _observation("nope")],
        new_facts=[kept, invented],
    )

    assert find_unquoted_evidence(result, turns) == ["nope", "I have a dog"]
    filtered = keep_quoted(result, turns)
    assert [o.evidence for o in filtered.skill_observations] == ["Yesterday I go"]
    assert filtered.new_facts == [kept]
