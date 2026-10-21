"""Coding-session orchestration: deterministic execution first, qualitative review second."""
import ast
import json
import random
from dataclasses import dataclass

from interview_coach.coding import runner
from interview_coach.crew import CodeReviewCrew
from interview_coach.pipeline import _model
from interview_coach.crew_coding_problem import CodingProblemCrew
from interview_coach.schemas import CodeEvaluation, CodingProblem, CodingProblemDraft

DIFFICULTY_LEVELS = {"easy": "junior", "medium": "mid", "hard": "senior"}
LANGUAGE_NAMES = {"Python": "python", "JavaScript": "javascript", "C#": "csharp"}
LANGUAGE_DISPLAY = {value: key for key, value in LANGUAGE_NAMES.items()}
MAX_DYNAMIC_GENERATION_ATTEMPTS = 3


@dataclass
class CodingSession:
    problem: dict
    visible_tests: list[dict]


def correctness_score(passed: int, total: int) -> int:
    """Map the pass ratio to 1 through 5 in four equal steps."""
    return 1 + round(passed / total / 0.25)


def _parse_generated_tests(raw_tests: str) -> list[dict]:
    text = raw_tests.strip()
    start = text.find("[")
    if start < 0:
        raise ValueError("Generated coding tests did not contain a JSON array.")
    candidate = text[start:]
    try:
        tests, _ = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError as json_err:
        try:
            tests = ast.literal_eval(candidate)
        except (SyntaxError, ValueError) as literal_err:
            literal_message = getattr(literal_err, "msg", str(literal_err))
            raise ValueError(
                "Generated coding tests were not valid JSON or a Python literal: "
                f"{json_err.msg}; {literal_message}."
            ) from literal_err
    if not isinstance(tests, list):
        raise ValueError("Generated coding tests must be a JSON array.")
    return tests


def _generate_dynamic_problem(difficulty: str, language: str, job_profile, resume_text: str) -> CodingSession:
    crew = CodingProblemCrew().crew()
    inputs = {
        "job_profile_json": job_profile.model_dump_json(),
        "resume_text": resume_text,
        "language": language,
        "difficulty": difficulty.lower(),
        "repair_instruction": "Return only the requested valid CodingProblemDraft.",
    }
    last_error = None
    for _ in range(MAX_DYNAMIC_GENERATION_ATTEMPTS):
        result = crew.kickoff(inputs=inputs)
        try:
            draft = _model(result, CodingProblemDraft)
            tests = _parse_generated_tests(draft.tests_json)
            problem = {
                "id": draft.problem_id,
                "title": draft.title,
                "prompt": draft.prompt,
                "function_name": draft.function_name,
                "starter_code": draft.starter_code,
                "tests": tests,
                "language": language,
                "difficulty": difficulty.lower(),
            }
            validated = CodingProblem.model_validate(problem)
            visible_tests = [test.model_dump() for test in validated.tests if test.visible]
            if len(visible_tests) < 2 or len(visible_tests) == len(validated.tests):
                raise ValueError("Generated coding problem must include visible and hidden tests.")
        except ValueError as err:
            last_error = err
            inputs["repair_instruction"] = (
                "The previous attempt was invalid. Return a complete, valid CodingProblemDraft "
                "with tests_json as a compact JSON array. Do not truncate or add commentary."
            )
            continue

        normalized = validated.model_dump()
        normalized["language"] = language
        normalized["difficulty"] = difficulty.lower()
        return CodingSession(problem=normalized, visible_tests=visible_tests)

    raise ValueError(
        f"Unable to generate a valid coding problem after "
        f"{MAX_DYNAMIC_GENERATION_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def get_problem(
    difficulty: str,
    language: str = "python",
    exclude: list | None = None,
    job_profile=None,
    resume_text: str = "",
) -> CodingSession:
    language = LANGUAGE_NAMES.get(language, language.lower())
    if language not in runner.available_languages():
        raise ValueError(f"{language} is not enabled on this deployment.")
    if job_profile is not None:
        return _generate_dynamic_problem(difficulty, language, job_profile, resume_text)

    level = DIFFICULTY_LEVELS.get(difficulty.lower(), difficulty.lower())
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
    report = runner.run_tests(code, problem["id"], language, problem)
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
        suggested = runner.run_tests(evaluation.improved_solution, problem["id"], language, problem)
        suggested["language"] = language
        evaluation.suggested_tests_passed = suggested["passed"]
        evaluation.suggested_tests_total = suggested["total"]
        if suggested["error"] or suggested["passed"] != suggested["total"]:
            evaluation.feedback.append("Suggested solution removed: it did not pass every sandbox test.")
            evaluation.improved_solution = ""
    return evaluation, {"submitted": report, "suggested": suggested}