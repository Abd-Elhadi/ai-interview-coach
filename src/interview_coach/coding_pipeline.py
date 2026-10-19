"""Coding-session orchestration: deterministic execution plus qualitative review."""
import json
from dataclasses import dataclass

from interview_coach.coding import runner
from interview_coach.crew import CodeReviewCrew
from interview_coach.pipeline import _model
from interview_coach.schemas import CodeEvaluation, Level

DIFFICULTY_LEVELS = {"easy": "junior", "medium": "mid", "hard": "senior"}
LANGUAGE_NAMES = {"Python": "python", "JavaScript": "javascript", "C#": "csharp"}
LANGUAGE_DISPLAY = {value: key for key, value in LANGUAGE_NAMES.items()}

@dataclass
class CodingSession:
    problem: dict
    visible_tests: list[dict]


def get_problem(difficulty: str, language: str = "python") -> CodingSession:
    level = DIFFICULTY_LEVELS.get(difficulty.lower(), difficulty.lower())
    language = LANGUAGE_NAMES.get(language, language.lower())
    if language not in runner.LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    problems = [
        problem
        for problem in runner.load_all_problems()
        if level in problem["levels"]
    ]
    if not problems:
        raise ValueError(f"No coding problem available for {level} level.")
    problem = dict(problems[0])
    problem["language"] = language
    problem["difficulty"] = next(
        (label for label, mapped in DIFFICULTY_LEVELS.items() if mapped == level), difficulty
    )
    problem["function_name"] = {
        "python": problem["function_name"],
        "javascript": runner.JS_FUNCTIONS[problem["id"]],
        "csharp": runner.CSHARP_FUNCTIONS[problem["id"]],
    }[language]
    problem["starter_code"] = runner.starter_code(problem["id"], language)
    visible_tests = [test for test in problem["tests"] if test["visible"]]
    return CodingSession(problem=problem, visible_tests=visible_tests)


def run_solution(code: str, problem_id: str, language: str = "python") -> dict:
    """Run both visible and hidden cases; runner output redacts hidden inputs."""
    return runner.run_tests(code, problem_id, language)


def review_solution(session: CodingSession, code: str) -> tuple[CodeEvaluation, dict]:
    language = session.problem["language"]
    test_report = run_solution(code, session.problem["id"], language)
    result = CodeReviewCrew().crew().kickoff(
        inputs={
            "problem_json": json.dumps(session.problem),
            "code": code,
            "test_results_json": json.dumps(test_report),
        }
    )
    evaluation = _model(result, CodeEvaluation)
    evaluation.problem_id = session.problem["id"]
    evaluation.tests_passed = test_report["passed"]
    evaluation.tests_total = test_report["total"]

    suggested_report = {"passed": 0, "total": 0, "error": None, "results": []}
    if evaluation.improved_solution.strip():
        suggested_report = run_solution(evaluation.improved_solution, session.problem["id"], language)
        evaluation.suggested_tests_passed = suggested_report["passed"]
        evaluation.suggested_tests_total = suggested_report["total"]
        if suggested_report["error"] or suggested_report["passed"] != suggested_report["total"]:
            evaluation.feedback.append("The suggested solution did not pass every sandbox test.")
            evaluation.improved_solution = ""
    test_report["language"] = language
    suggested_report["language"] = language
    return evaluation, {"submitted": test_report, "suggested": suggested_report}