import pytest
from pydantic import ValidationError

from interview_coach.schemas import DimensionScore, InterviewPlan, weighted_overall


def test_weighted_overall():
    scores = [
        DimensionScore(name="a", score=4, evidence="e", suggestion="s"),
        DimensionScore(name="b", score=2, evidence="e", suggestion="s"),
    ]
    assert weighted_overall(scores, {"a": 0.5, "b": 0.5}) == 3.0


def test_weighted_overall_rejects_unknown_dimensions():
    scores = [DimensionScore(name="x", score=3, evidence="e", suggestion="s")]
    with pytest.raises(ValueError):
        weighted_overall(scores, {"a": 1.0})


def test_plan_requires_three_questions():
    with pytest.raises(ValidationError):
        InterviewPlan(role="engineer", level="mid", questions=[])


def test_score_range():
    with pytest.raises(ValidationError):
        DimensionScore(name="a", score=6, evidence="e", suggestion="s")