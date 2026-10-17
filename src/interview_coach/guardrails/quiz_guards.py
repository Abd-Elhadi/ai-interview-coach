from typing import Any, Tuple

from crewai import TaskOutput

from interview_coach.guardrails.output_guards import _model
from interview_coach.schemas import MCQSet


def valid_mcqs(result: TaskOutput) -> Tuple[bool, Any]:
    quiz = _model(result, MCQSet)
    if quiz is None:
        return False, "Output must be valid MCQSet JSON."
    texts = [q.question.strip().lower() for q in quiz.questions]
    if len(set(texts)) != len(texts):
        return False, "Questions must be unique."
    for q in quiz.questions:
        if len({o.strip().lower() for o in q.options}) != 4:
            return False, f"Options must be distinct in {q.id}."
        if len(q.explanation.split()) < 5:
            return False, f"Explanation too short in {q.id}."
    if len(quiz.questions) >= 5 and len({q.correct_index for q in quiz.questions}) < 2:
        return False, "Vary the position of the correct answer."
    return True, result.raw