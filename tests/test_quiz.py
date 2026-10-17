from interview_coach.quiz_pipeline import score_mcqs
from interview_coach.schemas import MCQQuestion, MCQSet


def _q(i, correct):
    return MCQQuestion(
        id=f"m{i}", question=f"Question {i}?", options=["a", "b", "c", "d"],
        correct_index=correct, skill="python", explanation="Because this is the right answer.",
    )


def test_score_mcqs():
    mcqs = MCQSet(questions=[_q(1, 0), _q(2, 1), _q(3, 2)])
    out = score_mcqs(mcqs, [0, 1, None])
    assert out["correct"] == 2 and out["total"] == 3 and out["ratio"] == 0.67