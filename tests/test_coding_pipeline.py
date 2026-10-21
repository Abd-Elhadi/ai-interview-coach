import pytest

from interview_coach import coding_pipeline
from interview_coach.coding import runner
from interview_coach.schemas import CodeEvaluation, CodingProblemDraft, JobProfile
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


def test_dynamic_problem_uses_resume_and_job_profile(monkeypatch):
    profile = JobProfile(
        title="Backend Engineer",
        seniority="mid",
        required_skills=["Python", "APIs"],
        responsibilities=["Build services"],
        interview_themes=["Reliability"],
    )
    draft = CodingProblemDraft(
        problem_id="c1",
        title="Service Request Matching",
        prompt="Return matching request indices.",
        function_name="match_requests",
        starter_code="def match_requests(items, target):\n    pass\n",
        tests_json=(
            '[{"args":[[2, 7, 11], 9],"expected":[0, 1],"visible":true},'
            '{"args":[[1, 2], 3],"expected":[0, 1],"visible":false},'
            '{"args":[[4, 5], 9],"expected":[0, 1],"visible":true}]'
        ),
    )
    captured = {}

    class FakeCrew:
        def crew(self):
            return self

        def kickoff(self, inputs):
            captured.update(inputs)
            return SimpleNamespace(pydantic=draft)

    monkeypatch.setattr(coding_pipeline, "CodingProblemCrew", FakeCrew)
    session = coding_pipeline.get_problem(
        "medium",
        "JavaScript",
        job_profile=profile,
        resume_text="Built Python APIs and service integrations.",
    )

    assert session.problem["language"] == "javascript"
    assert session.problem["title"] == "Service Request Matching"
    assert len(session.visible_tests) == 2
    assert "Backend Engineer" in captured["job_profile_json"]
    assert "Python APIs" in captured["resume_text"]


def test_dynamic_problem_retries_malformed_generated_tests(monkeypatch):
    profile = JobProfile(
        title="Backend Engineer",
        seniority="mid",
        required_skills=["Python"],
        responsibilities=["Build services"],
        interview_themes=["Reliability"],
    )
    valid_draft = CodingProblemDraft(
        problem_id="c1",
        title="Request Matching",
        prompt="Return matching request indices.",
        function_name="match_requests",
        starter_code="def match_requests(items, target):\n    pass\n",
        tests_json=(
            '[{"args":[[2, 7, 11], 9],"expected":[0, 1],"visible":true},'
            '{"args":[[1, 2], 3],"expected":[0, 1],"visible":false},'
            '{"args":[[4, 5], 9],"expected":[0, 1],"visible":true}]'
        ),
    )
    responses = iter(
        [
            SimpleNamespace(
                pydantic=CodingProblemDraft(
                    problem_id="c1",
                    title="Request Matching",
                    prompt="Return matching request indices.",
                    function_name="match_requests",
                    starter_code="def match_requests(items, target):\n    pass\n",
                    tests_json="[{'args': [{'items': 1}",
                )
            ),
            SimpleNamespace(pydantic=valid_draft),
        ]
    )

    class FakeCrew:
        def crew(self):
            return self

        def kickoff(self, inputs):
            return next(responses)

    monkeypatch.setattr(coding_pipeline, "CodingProblemCrew", FakeCrew)
    session = coding_pipeline.get_problem("medium", "Python", job_profile=profile)

    assert session.problem["title"] == "Request Matching"


def test_generated_tests_allow_trailing_model_text():
    raw = '[{"args":[[1, 2], 3],"expected":[0, 1],"visible":true}] Extra explanation.'
    assert coding_pipeline._parse_generated_tests(raw)[0]["expected"] == [0, 1]


def test_generated_tests_allow_python_literal_format():
    raw = "[{'args': [['hello']], 'expected': 1, 'visible': True}]"
    assert coding_pipeline._parse_generated_tests(raw)[0]["expected"] == 1


def test_generated_tests_report_parse_errors_without_attribute_error():
    with pytest.raises(ValueError, match="not valid JSON or a Python literal"):
        coding_pipeline._parse_generated_tests("[{'args': invalid}]")


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


def test_other_languages_require_available_runtime(monkeypatch):
    monkeypatch.delenv("ENABLED_LANGUAGES", raising=False)
    assert "python" in runner.available_languages()
    monkeypatch.setenv("ENABLED_LANGUAGES", "python")
    with pytest.raises(ValueError):
        runner.run_tests("x", "c1", "javascript")