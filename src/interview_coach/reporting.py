import tempfile
from pathlib import Path

from interview_coach.schemas import FinalReport


def report_to_markdown(report: FinalReport) -> str:
    lines = ["# Interview Coaching Report", "", f"Overall score: {report.overall_score:.1f} / 5", "", "## Summary", report.summary, "", "## Top strengths"]
    lines += [f"- {item}" for item in report.top_strengths]
    lines += ["", "## Top gaps"] + [f"- {item}" for item in report.top_gaps]
    lines += ["", "## Action plan"] + [f"{i}. {item}" for i, item in enumerate(report.action_plan, 1)]
    lines += ["", "## Per question"]
    for ev in report.per_question:
        lines += ["", f"### {ev.question_id} ({ev.question_type}), score {ev.overall_score:.1f} / 5"]
        lines += [f"- {d.name}: {d.score}/5. {d.suggestion}" for d in ev.dimension_scores]
        if ev.improved_answer:
            lines += ["", "Improved answer:", ev.improved_answer]
    lines += ["", report.disclaimer]
    return "\n".join(lines)


def save_report(text: str) -> str:
    folder = Path(tempfile.mkdtemp(prefix="report_"))
    path = folder / "interview_report.md"
    path.write_text(text, encoding="utf-8")
    return str(path)