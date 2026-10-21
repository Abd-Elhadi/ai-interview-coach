import re
from typing import Any, Tuple

from crewai import TaskOutput

from interview_coach.rubrics import bank_ids, dimension_names
from interview_coach.schemas import AnswerEvaluation, CodeEvaluation, FinalReport, InterviewPlan

NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
EXPECTED_ORDER = ["behavioral", "technical", "situational"]


def _model(result: TaskOutput, cls):
    if isinstance(result.pydantic, cls):
        return result.pydantic
    try:
        return cls.model_validate_json(result.raw)
    except Exception:
        return None


def valid_plan(result: TaskOutput) -> Tuple[bool, Any]:
    plan = _model(result, InterviewPlan)
    if plan is None:
        return False, "Output must be valid InterviewPlan JSON."
    if [q.category for q in plan.questions] != EXPECTED_ORDER:
        return False, "Questions must be exactly: behavioral, technical, situational, in that order."
    if any(not q.source_question_id.strip() for q in plan.questions):
        return False, "Every question needs the source_question_id returned by the MCP tool."
    known = bank_ids()
    if any(q.source_question_id not in known for q in plan.questions):
        return False, "source_question_id must be an id returned by get_interview_questions."
    if len({q.source_question_id for q in plan.questions}) != len(plan.questions):
        return False, "Each question must come from a different source question."
    return True, result.raw


def valid_evaluation(result: TaskOutput) -> Tuple[bool, Any]:
    ev = _model(result, AnswerEvaluation)
    if ev is None:
        return False, "Output must be valid AnswerEvaluation JSON."
    expected = dimension_names(ev.question_type)
    got = {d.name for d in ev.dimension_scores}
    if got != expected:
        return False, f"Score exactly these rubric dimensions: {sorted(expected)}."
    if any(len(d.evidence.split()) < 4 for d in ev.dimension_scores):
        return False, "Each score needs an evidence note of at least 4 words that points to the answer."
    if not ev.improvements:
        return False, "Provide at least one improvement."
    if not 20 <= len(ev.improved_answer.split()) <= 260:
        return False, "improved_answer must be 20 to 260 words."
    return True, result.raw


def valid_report(result: TaskOutput) -> Tuple[bool, Any]:
    report = _model(result, FinalReport)
    if report is None:
        return False, "Output must be valid FinalReport JSON."
    if not (report.action_plan and report.top_strengths and report.top_gaps):
        return False, "Report needs strengths, gaps, and an action plan."
    return True, result.raw


def valid_code_evaluation(result: TaskOutput) -> Tuple[bool, Any]:
    evaluation = _model(result, CodeEvaluation)
    if evaluation is None:
        return False, "Output must be valid CodeEvaluation JSON."
    if evaluation.tests_passed > evaluation.tests_total:
        return False, "tests_passed cannot exceed tests_total."
    if not evaluation.feedback:
        return False, "Provide at least one concrete code-review feedback item."
    return True, result.raw


def unsupported_numbers(text: str, source: str) -> list[str]:
    """Numbers in text that do not appear in source. Used to block invented metrics."""
    allowed = set(NUMBER.findall(source))
    return sorted(n for n in set(NUMBER.findall(text)) if n not in allowed)