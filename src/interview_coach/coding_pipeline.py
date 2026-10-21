"""Coding-session orchestration: deterministic execution first, qualitative review second."""
import json
import random
from dataclasses import dataclass

from interview_coach.coding import runner
from interview_coach.crew import CodeReviewCrew
from interview_coach.pipeline import _model
from interview_coach.schemas import CodeEvaluation

DIFFICULTY_LEVELS = {"easy": "junior", "medium": "mid", "hard": "senior"}
LANGUAGE_NAMES = {"Python": "python", "JavaScript": "javascript", "C#": "csharp"}
LANGUAGE_DISPLAY = {value: key for key, value in LANGUAGE_NAMES.items()}


@dataclass
class CodingSession:
    problem: dict
    visible_tests: list[dict]


def correctness_score(passed: int, total: int) -> int:
    """Map the pass ratio to 1 through 5 in four equal steps."""
    return 1 + round(passed / total / 0.25)


def get_problem(difficulty: str, language: str = "python", exclude: list | None = None) -> CodingSession:
    level = DIFFICULTY_LEVELS.get(difficulty.lower(), difficulty.lower())
    language = LANGUAGE_NAMES.get(language, language.lower())
    if language not in runner.available_languages():
        raise ValueError(f"{language} is not enabled on this deployment.")
    problems = [p for p in runner.load_all_problems() if level in p["levels"]]
    if not problems:
        raise ValueError(f"No coding problem available for {level} level.")
    excluded = set(exclude or [])
    problem = dict(random.choice([p for p in problems if p["id"] not in excluded] or problems))
    problem["language"] = language
    problem["difficulty"] = next((k for k, v in DIFFICULTY_LEVELS.items() if v == level), difficulty)
    problem["function_name"] = {
        "python": problem["function_name"],
        "javascript": runner.JS_FUNCTIONS[problem["id"]],
        "csharp": runner.CSHARP_FUNCTIONS[problem["id"]],
    }[language]
    problem["starter_code"] = runner.starter_code(problem["id"], language)
    visible_tests = [t for t in problem.pop("tests") if t["visible"]]  # hidden tests never leave the runner
    return CodingSession(problem=problem, visible_tests=visible_tests)


def review_solution(session: CodingSession, code: str) -> tuple:
    problem = session.problem
    language = problem["language"]
    report = runner.run_tests(code, problem["id"], language)
    report["language"] = language
    empty = {"passed": 0, "total": 0, "error": None, "results": [], "language": language}
    if report["error"]:
        return None, {"submitted": report, "suggested": empty}  # rejected code never reaches the LLM

    payload = dict(problem)
    payload["visible_tests"] = session.visible_tests
    result = CodeReviewCrew().crew().kickoff(
        inputs={
            "problem_json": json.dumps(payload),
            "code": code,
            "test_results_json": json.dumps(report),
        }
    )
    evaluation = _model(result, CodeEvaluation)
    evaluation.problem_id = problem["id"]
    evaluation.tests_passed = report["passed"]
    evaluation.tests_total = report["total"]
    evaluation.correctness_score = correctness_score(report["passed"], report["total"])

    suggested = dict(empty)
    if evaluation.improved_solution.strip():
        suggested = runner.run_tests(evaluation.improved_solution, problem["id"], language)
        suggested["language"] = language
        evaluation.suggested_tests_passed = suggested["passed"]
        evaluation.suggested_tests_total = suggested["total"]
        if suggested["error"] or suggested["passed"] != suggested["total"]:
            evaluation.feedback.append("Suggested solution removed: it did not pass every sandbox test.")
            evaluation.improved_solution = ""
    return evaluation, {"submitted": report, "suggested": suggested}