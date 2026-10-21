import pytest

from interview_coach import coding_pipeline
from interview_coach.coding import runner
from interview_coach.schemas import CodeEvaluation
from types import SimpleNamespace

GOOD = """
def two_sum(nums, target):
    seen = {}
    for i, number in enumerate(nums):
        if target - number in seen:
            return [seen[target - number], i]
        seen[number] = i
"""


def _evaluation(solution: str) -> CodeEvaluation:
    return CodeEvaluation(
        problem_id="wrong", tests_passed=0, tests_total=1, correctness_score=1, quality_score=3,
        complexity_notes="O(n) time, O(n) space.", feedback=["Use a lookup table."], improved_solution=solution,
    )


def _fake_crew(evaluation):
    class FakeCrew:
        def crew(self):
            return self

        def kickoff(self, inputs):
            assert "tests" not in inputs["problem_json"] or '"visible_tests"' in inputs["problem_json"]
            return SimpleNamespace(pydantic=evaluation)

    return FakeCrew


def test_problem_has_no_hidden_tests():
    session = coding_pipeline.get_problem("easy", "Python")
    assert "tests" not in session.problem
    assert session.visible_tests and all(t["visible"] for t in session.visible_tests)


def test_problems_vary_and_respect_exclusions():
    seen = {coding_pipeline.get_problem("medium", "Python").problem["id"] for _ in range(40)}
    assert len(seen) > 1
    assert coding_pipeline.get_problem("easy", "Python", exclude=["c1"]).problem["id"] == "c2"


def test_review_rechecks_suggestion(monkeypatch):
    session = coding_pipeline.get_problem("easy", "Python", exclude=["c2"])
    monkeypatch.setattr(coding_pipeline, "CodeReviewCrew", _fake_crew(_evaluation(GOOD)))
    reviewed, reports = coding_pipeline.review_solution(session, GOOD)
    assert reviewed.problem_id == "c1"
    assert reviewed.tests_passed == reviewed.tests_total == 4
    assert reviewed.correctness_score == 5
    assert reports["suggested"]["passed"] == 4


def test_bad_suggestion_is_removed(monkeypatch):
    session = coding_pipeline.get_problem("easy", "Python", exclude=["c2"])
    wrong = "def two_sum(nums, target):\n    return [0, 0]\n"
    monkeypatch.setattr(coding_pipeline, "CodeReviewCrew", _fake_crew(_evaluation(wrong)))
    reviewed, _ = coding_pipeline.review_solution(session, GOOD)
    assert reviewed.improved_solution == ""


def test_rejected_code_never_reaches_the_llm(monkeypatch):
    class Boom:
        def crew(self):
            raise AssertionError("The LLM must not be called for rejected code")

    monkeypatch.setattr(coding_pipeline, "CodeReviewCrew", Boom)
    session = coding_pipeline.get_problem("easy", "Python", exclude=["c2"])
    evaluation, reports = coding_pipeline.review_solution(
        session, "import os\ndef two_sum(nums, target):\n    return []\n"
    )
    assert evaluation is None
    assert "Import not allowed" in reports["submitted"]["error"]


def test_other_languages_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLED_LANGUAGES", raising=False)
    assert runner.available_languages() == ["python"]
    with pytest.raises(ValueError):
        runner.run_tests("x", "c1", "javascript")