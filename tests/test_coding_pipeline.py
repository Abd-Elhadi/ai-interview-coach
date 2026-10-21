from types import SimpleNamespace

from interview_coach import coding_pipeline
from interview_coach.schemas import CodeEvaluation, CodingProblem, JobProfile


GOOD = """
def two_sum(nums, target):
    seen = {}
    for i, number in enumerate(nums):
        if target - number in seen:
            return [seen[target - number], i]
        seen[number] = i
"""


def test_get_problem_exposes_only_visible_tests_for_prompting():
    session = coding_pipeline.get_problem("easy", "Python")
    assert session.problem["id"] == "c1"
    assert session.problem["difficulty"] == "easy"
    assert session.problem["language"] == "python"
    assert session.visible_tests
    assert all(test["visible"] for test in session.visible_tests)


def test_get_problem_builds_javascript_variant():
    session = coding_pipeline.get_problem("medium", "JavaScript")
    assert session.problem["language"] == "javascript"
    assert "module.exports" in session.problem["starter_code"]


def test_get_problem_generates_from_job_profile(monkeypatch):
    profile = JobProfile(
        title="Backend Engineer",
        seniority="mid",
        required_skills=["Python", "APIs"],
        responsibilities=["Build services"],
        interview_themes=["Reliability"],
    )
    generated = {
        "id": "generated-1",
        "title": "API Request Aggregation",
        "prompt": "Aggregate request counts by route.",
        "function_name": "aggregate_requests",
        "starter_code": "def aggregate_requests(events):\n    pass\n",
        "tests": [
            {"args": [[{"route": "/health"}]], "expected": {"/health": 1}, "visible": True},
            {"args": [[]], "expected": {}, "visible": False},
            {"args": [[{"route": "/api"}]], "expected": {"/api": 1}, "visible": True},
        ],
    }
    captured = {}

    class FakeCrew:
        def crew(self):
            return self

        def kickoff(self, inputs):
            captured.update(inputs)
            return SimpleNamespace(pydantic=CodingProblem.model_validate(generated))

    monkeypatch.setattr(coding_pipeline, "CodingProblemCrew", FakeCrew)
    session = coding_pipeline.get_problem("medium", "Python", profile)

    assert session.problem["title"] == "API Request Aggregation"
    assert session.problem["language"] == "python"
    assert len(session.visible_tests) == 2
    assert '"Backend Engineer"' in captured["job_profile_json"]


def test_review_solution_rechecks_agent_suggestion(monkeypatch):
    session = coding_pipeline.get_problem("junior")
    suggestion = GOOD
    evaluation = CodeEvaluation(
        problem_id="wrong",
        tests_passed=0,
        tests_total=1,
        correctness_score=1,
        quality_score=3,
        complexity_notes="O(n) time, O(n) space.",
        feedback=["Use a lookup table."],
        improved_solution=suggestion,
    )

    class FakeCrew:
        def crew(self):
            return self

        def kickoff(self, inputs):
            return SimpleNamespace(pydantic=evaluation)

    monkeypatch.setattr(coding_pipeline, "CodeReviewCrew", FakeCrew)
    reviewed, reports = coding_pipeline.review_solution(session, GOOD)

    assert reviewed.problem_id == "c1"
    assert reviewed.tests_passed == reviewed.tests_total == 4
    assert reviewed.suggested_tests_passed == reviewed.suggested_tests_total == 4
    assert reports["submitted"]["passed"] == 4
    assert reports["suggested"]["passed"] == 4