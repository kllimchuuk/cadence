import pytest
from pydantic import ValidationError

from orchestration.schemas import SessionAnalysisResult


def _kwargs(**overrides: object) -> dict[str, object]:
    base = {
        "grammar_findings": [],
        "vocabulary_findings": [],
        "fluency_findings": {},
        "task_completion": {},
        "focus_points": ["Practice past-tense verbs"],
        "skill_observations": [],
        "new_facts": [],
    }
    base.update(overrides)
    return base


def test_a_single_focus_point_is_accepted() -> None:
    result = SessionAnalysisResult(**_kwargs(focus_points=["one thing"]))
    assert result.focus_points == ["one thing"]


def test_three_focus_points_are_accepted() -> None:
    result = SessionAnalysisResult(**_kwargs(focus_points=["a", "b", "c"]))
    assert result.focus_points == ["a", "b", "c"]


def test_zero_focus_points_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SessionAnalysisResult(**_kwargs(focus_points=[]))


def test_more_than_three_focus_points_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SessionAnalysisResult(**_kwargs(focus_points=["a", "b", "c", "d"]))
