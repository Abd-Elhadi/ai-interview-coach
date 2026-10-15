"""Stub backend for the UI shell. Keep function signatures; swap bodies for crew calls."""
from pathlib import Path

from pypdf import PdfReader

MAX_BYTES = 2_000_000
ALLOWED = {".txt", ".pdf"}
MIN_ANSWER_WORDS = 10


def load_resume(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("Resume must be a .pdf or .txt file.")
    if p.stat().st_size > MAX_BYTES:
        raise ValueError("Resume exceeds 2 MB.")
    if suffix == ".pdf":
        reader = PdfReader(str(p))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return p.read_text(errors="ignore")


def plan_interview(resume_text: str, job_text: str) -> list[dict]:
    return [
        {"id": "q1", "category": "behavioral", "question": "Tell me about a time you delivered a project under a tight deadline."},
        {"id": "q2", "category": "technical", "question": "Explain how you would design a REST API for user accounts."},
        {"id": "q3", "category": "situational", "question": "You find a serious bug right before a release. What do you do?"},
    ]


def evaluate_answer(question: dict, answer: str) -> dict:
    words = len(answer.split())
    return {
        "question_id": question["id"],
        "question_type": question["category"],
        "overall_score": 3.0,
        "strengths": [f"Answer length: {words} words."],
        "gaps": ["Stub evaluation. Real rubric scoring arrives with the crew."],
        "improvements": ["Add a measurable result."],
    }


def draft_report(evals: list[dict]) -> str:
    if not evals:
        return ""
    avg = sum(e["overall_score"] for e in evals) / len(evals)
    lines = [f"Overall score: {avg:.1f} / 5", "", "Per question:"]
    for e in evals:
        lines.append(f"- {e['question_id']} ({e['question_type']}): {e['overall_score']:.1f}")
        lines.append(f"  Gaps: {'; '.join(e['gaps'])}")
        lines.append(f"  Improve: {'; '.join(e['improvements'])}")
    lines += ["", "Practice coaching estimate. Not a hiring decision."]
    return "\n".join(lines)