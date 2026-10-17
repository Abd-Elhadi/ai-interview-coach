from interview_coach.crew_quiz import MCQCrew
from interview_coach.pipeline import InterviewSession, _model
from interview_coach.schemas import MCQSet


def generate_mcqs(session: InterviewSession, count: int = 5) -> MCQSet:
    result = MCQCrew().crew().kickoff(
        inputs={
            "job_profile_json": session.job_profile.model_dump_json(),
            "seniority": session.job_profile.seniority,
            "count": count,
        }
    )
    quiz = _model(result, MCQSet)
    quiz.questions = quiz.questions[:count]
    return quiz


def score_mcqs(mcqs: MCQSet, picks: list) -> dict:
    correct = sum(1 for q, p in zip(mcqs.questions, picks) if p == q.correct_index)
    total = len(mcqs.questions)
    return {"correct": correct, "total": total, "ratio": round(correct / total, 2)}