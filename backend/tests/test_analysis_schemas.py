import pytest
from pydantic import ValidationError

from analysis.schemas import SessionAnalysisResult


def _kwargs(**overrides: object) -> dict[str, object]:
    base = {
        "grammar_findings": [],
        "vocabulary_findings": [],
        "fluency_findings": {"summary": "Steady pace."},
        "task_completion": {"goals": []},
        "focus_points": [_point("Practice past-tense verbs")],
        "skill_observations": [],
        "new_facts": [],
    }
    base.update(overrides)
    return base


def _point(text: str) -> dict[str, str]:
    return {"text": text, "evidence": "Yesterday I go"}


def test_a_single_focus_point_is_accepted() -> None:
    result = SessionAnalysisResult(**_kwargs(focus_points=[_point("one thing")]))
    assert [point.text for point in result.focus_points] == ["one thing"]


def test_three_focus_points_are_accepted() -> None:
    points = [_point("a"), _point("b"), _point("c")]
    result = SessionAnalysisResult(**_kwargs(focus_points=points))
    assert len(result.focus_points) == 3


def test_no_focus_points_is_accepted() -> None:
    result = SessionAnalysisResult(**_kwargs(focus_points=[]))
    assert result.focus_points == []


def test_more_than_three_focus_points_is_rejected() -> None:
    points = [_point(text) for text in "abcd"]
    with pytest.raises(ValidationError):
        SessionAnalysisResult(**_kwargs(focus_points=points))
