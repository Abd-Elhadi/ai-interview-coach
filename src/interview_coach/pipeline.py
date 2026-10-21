"""Orchestrates the three crews plus the deterministic checks around them."""
import json
import re
from dataclasses import dataclass, field

from interview_coach.crew import EvaluationCrew, PlanningCrew, ReportCrew
from interview_coach.guardrails import input_guards, output_guards
from interview_coach.rubrics import weights_for
from interview_coach.schemas import (
    AnswerEvaluation,
    FinalReport,
    InterviewPlan,
    JobProfile,
    ResumeProfile,
    weighted_overall,
)

FILLERS = re.compile(r"\b(um+|uh+|erm|you know)\b", re.IGNORECASE)


@dataclass
class InterviewSession:
    resume_text: str
    job_profile: JobProfile
    resume_profile: ResumeProfile
    plan: InterviewPlan
    warnings: list[str] = field(default_factory=list)
    evaluations: list[AnswerEvaluation] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)

def _history(session: InterviewSession) -> str:
    if not session.evaluations:
        return "None yet."
    return "\n".join(
        f"- {e.question_type}: score {e.overall_score:.1f}; gaps: {'; '.join(e.gaps[:2])}"
        for e in session.evaluations
    )

def _model(output, cls):
    model = getattr(output, "pydantic", None)
    if not isinstance(model, cls):
        raise RuntimeError(f"Agent did not return a valid {cls.__name__}. Try again.")
    return model


def start_session(resume_raw: str, job_raw: str, seen_ids: list[str] | None = None) -> InterviewSession:
    resume = input_guards.check_text(resume_raw, "resume", 200, 20000)
    job = input_guards.check_text(job_raw, "job description", 100, 10000)
    result = PlanningCrew().crew().kickoff(
        inputs={
            "job_description": job.text,
            "resume_text": resume.text,
            "seen_question_ids": json.dumps(seen_ids or []),
        }
    )
    outputs = result.tasks_output
    plan = _model(outputs[2], InterviewPlan)
    return InterviewSession(
        resume_text=resume.text,
        job_profile=_model(outputs[0], JobProfile),
        resume_profile=_model(outputs[1], ResumeProfile),
        plan=plan,
        warnings=resume.warnings + job.warnings,
        question_ids=[q.source_question_id for q in plan.questions],
    )


def evaluate_answer(session: InterviewSession, idx: int, answer_raw: str) -> AnswerEvaluation:
    answer = input_guards.check_text(answer_raw, "answer", 40, 6000)
    question = session.plan.questions[idx]
    result = EvaluationCrew().crew().kickoff(
        inputs={
            "question_type": question.category,
            "question": question.question,
            "answer": answer.text,
            "history": _history(session),
        }
    )
    ev = _model(result, AnswerEvaluation)
    # Deterministic fields: the LLM scores dimensions, Python computes the rest.
    ev.question_id = question.id
    ev.question_type = question.category
    ev.overall_score = weighted_overall(ev.dimension_scores, weights_for(question.category))
    ev.filler_word_count = len(FILLERS.findall(answer.text))
    invented = output_guards.unsupported_numbers(ev.improved_answer, answer.text)
    if invented:
        ev.improved_answer = ""
        ev.gaps.append("Improved answer removed: it contained figures not found in your answer.")
    session.evaluations.append(ev)
    return ev


def build_report(session: InterviewSession) -> FinalReport:
    payload = json.dumps([e.model_dump() for e in session.evaluations])
    result = ReportCrew().crew().kickoff(inputs={"evaluations_json": payload})
    report = _model(result, FinalReport)
    report.per_question = session.evaluations
    report.overall_score = round(
        sum(e.overall_score for e in session.evaluations) / len(session.evaluations), 2
    )
    report.approved = False
    return report