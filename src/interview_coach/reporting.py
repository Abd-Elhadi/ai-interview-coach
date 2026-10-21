import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

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


def _clean(text: str) -> str:
    """Standard PDF fonts use a Western encoding. Replace anything outside it."""
    return text.encode("cp1252", "replace").decode("cp1252")


def report_to_pdf(text: str) -> str:
    styles = getSampleStyleSheet()
    bullet = ParagraphStyle("bullet", parent=styles["BodyText"], leftIndent=14, bulletIndent=2)
    story = []
    for raw in text.splitlines():
        line = _clean(raw.rstrip())
        if not line.strip():
            story.append(Spacer(1, 6))
        elif line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["Heading3"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["Heading1"]))
        elif line.startswith("- "):
            story.append(Paragraph(escape(line[2:]), bullet, bulletText="\u2022"))
        else:
            story.append(Paragraph(escape(line), styles["BodyText"]))
    folder = Path(tempfile.mkdtemp(prefix="report_"))
    path = folder / "interview_report.pdf"
    SimpleDocTemplate(str(path), pagesize=letter, title="Interview Coaching Report").build(story)
    return str(path)