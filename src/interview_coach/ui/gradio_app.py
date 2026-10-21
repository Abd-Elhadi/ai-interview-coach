import shutil
import uuid
from pathlib import Path

import gradio as gr

from interview_coach import auth, emailer, pipeline, reporting
from interview_coach.ui import backend, coding_tab
from interview_coach.ui.quiz_tab import build as build_quiz_tab
from mcp_server.server import AUDIO_DIR, synthesize_question, transcribe_answer

LOADER_CSS = """
.coach-loader {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin: 10px 0;
    padding: 10px 14px;
    border: 1px solid #c8d6e5;
    border-radius: 10px;
    background: #f4f8fb;
    color: #24445c;
    font-size: 0.95rem;
}
.coach-loader-dot {
    width: 14px;
    height: 14px;
    border: 2px solid #b7c8d8;
    border-top-color: #2878a8;
    border-radius: 50%;
    animation: coach-spin 0.8s linear infinite;
}
@keyframes coach-spin { to { transform: rotate(360deg); } }
"""


def _need_user(user):
    if not user:
        raise gr.Error("Sign in first.")
    return user


def _cell(text) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def _question_md(session, idx: int) -> str:
    q = session.plan.questions[idx]
    return f"### Question {idx + 1} of {len(session.plan.questions)} ({q.category})\n\n{q.question}"


def _question_audio(session, idx: int):
    if idx >= len(session.plan.questions):
        return None
    try:
        filename = synthesize_question(session.plan.questions[idx].question)
    except Exception as err:
        gr.Warning(f"Could not play the question: {err}")
        return None
    path = (AUDIO_DIR / Path(filename).name).resolve()
    if not path.is_file() or AUDIO_DIR not in path.parents:
        gr.Warning("Question audio was not created.")
        return None
    return str(path)


def _feedback_md(ev) -> str:
    rows = [
        f"| {_cell(d.name)} | {d.score}/5 | {_cell(d.evidence)} | {_cell(d.suggestion)} |"
        for d in ev.dimension_scores
    ]
    parts = [f"### Score {ev.overall_score:.1f} / 5", "", "| Dimension | Score | Evidence | Suggestion |", "|---|---|---|---|"] + rows
    parts += ["", "Strengths: " + "; ".join(ev.strengths), "", "Gaps: " + "; ".join(ev.gaps), "", "Improve: " + "; ".join(ev.improvements)]
    if ev.filler_word_count:
        parts += ["", f"Filler words detected: {ev.filler_word_count}"]
    if ev.improved_answer:
        parts += ["", "#### Improved answer", ev.improved_answer]
    return "\n".join(parts)


def _signed_in(user: dict):
    return user, gr.update(visible=False), gr.update(visible=True), f"Signed in as {user['email']}", "", "", ""


def sign_in(email, password):
    try:
        return _signed_in(auth.sign_in(email, password))
    except auth.AuthError as err:
        raise gr.Error(str(err))


def sign_up(email, password, confirm):
    try:
        return _signed_in(auth.sign_up(email, password, confirm))
    except auth.AuthError as err:
        raise gr.Error(str(err))


def sign_out():
    return None, {}, gr.update(visible=True), gr.update(visible=False), "", gr.update(visible=False), gr.update(visible=False)


def start(resume_path, job_text, state, user):
    _need_user(user)
    if not resume_path or not (job_text or "").strip():
        raise gr.Error("Upload a resume and paste a job description.")
    try:
        resume_text = backend.load_resume(resume_path)
        session = pipeline.start_session(resume_text, job_text, auth.seen_question_ids(user["id"]))
        auth.mark_seen(user["id"], session.question_ids)
    except ValueError as err:
        raise gr.Error(str(err))
    except Exception as err:
        raise gr.Error(f"Could not start the interview: {err}")
    state = {"session": session, "idx": 0, "approved": False}
    notes = "\n".join(f"- {w}" for w in session.warnings)
    notes_md = f"Privacy notes:\n{notes}" if notes else ""
    return (
        state,
        _question_md(session, 0),
        gr.update(visible=True),
        "",
        gr.update(visible=False),
        "",
        gr.update(value=None, visible=False),
        notes_md,
        _question_audio(session, 0),
        "",
        None,
    )


def transcribe(audio_path, state):
    if not state or "session" not in state:
        raise gr.Error("Start the interview first.")
    if not audio_path:
        raise gr.Error("Record an answer before transcribing.")
    src = Path(audio_path)
    suffix = src.suffix.lower()
    if not src.is_file() or suffix not in {".wav", ".webm", ".mp3"}:
        raise gr.Error("Record a .wav, .webm, or .mp3 answer.")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = (AUDIO_DIR / filename).resolve()
    if AUDIO_DIR not in dest.parents:
        raise gr.Error("Could not store the recording.")
    shutil.copyfile(src, dest)
    try:
        return transcribe_answer(filename)
    except Exception as err:
        raise gr.Error(f"Transcription failed: {err}")


def submit(answer, state):
    if not state or "session" not in state:
        raise gr.Error("Start the interview first.")
    session = state["session"]
    if state["idx"] >= len(session.plan.questions):
        raise gr.Error("The interview is already complete.")
    if len((answer or "").split()) < backend.MIN_ANSWER_WORDS:
        raise gr.Error(f"Answer needs at least {backend.MIN_ANSWER_WORDS} words.")
    try:
        ev = pipeline.evaluate_answer(session, state["idx"], answer)
    except ValueError as err:
        raise gr.Error(str(err))
    except Exception as err:
        raise gr.Error(f"Evaluation failed: {err}")
    state["idx"] += 1
    if state["idx"] < len(session.plan.questions):
        return (
            state, _question_md(session, state["idx"]), "", _feedback_md(ev),
            gr.update(visible=False), "", _question_audio(session, state["idx"]), None,
        )
    try:
        draft = reporting.report_to_markdown(pipeline.build_report(session))
    except Exception as err:
        raise gr.Error(f"Report generation failed: {err}")
    return state, "### Interview complete", "", _feedback_md(ev), gr.update(visible=True), draft, None, None


def approve(draft_text, state, user):
    _need_user(user)
    if not state or not state.get("session") or not state["session"].evaluations:
        raise gr.Error("Nothing to approve yet.")
    if state.get("approved"):
        raise gr.Error("This report is already approved.")
    if not (draft_text or "").strip():
        raise gr.Error("The report is empty.")
    evaluations = state["session"].evaluations
    score = round(sum(e.overall_score for e in evaluations) / len(evaluations), 2)
    md_path = reporting.save_report(draft_text)
    pdf_path = reporting.report_to_pdf(draft_text)
    auth.save_report(user["id"], score, draft_text)
    state.update({"approved": True, "pdf_path": pdf_path, "score": score})
    return (
        state,
        "### Final report approved and saved to your account.",
        gr.update(value=md_path, visible=True),
        gr.update(value=pdf_path, visible=True),
        gr.update(visible=emailer.configured()),
        "",
    )


def reject(state):
    if state:
        state["approved"] = False
    return (
        state,
        "### Report rejected. Edit the draft or start a new interview.",
        gr.update(value=None, visible=False),
        gr.update(value=None, visible=False),
        gr.update(visible=False),
    )


def email_report(state, user):
    _need_user(user)
    if not state or not state.get("approved") or not state.get("pdf_path"):
        raise gr.Error("Approve the report first.")
    try:
        emailer.send_report(user["id"], user["email"], state["pdf_path"], state["score"])
    except emailer.EmailError as err:
        raise gr.Error(str(err))
    return f"Report sent to {user['email']}."


def refresh_reports(user):
    _need_user(user)
    rows = auth.list_reports(user["id"])
    choices = [(f"{r['created_at']} | {r['overall_score']:.1f}/5", r["id"]) for r in rows]
    return gr.update(choices=choices, value=None), ""


def show_report(report_id, user):
    _need_user(user)
    if report_id is None:
        return ""
    return auth.get_report(user["id"], int(report_id)) or "Report not found."


def build_app() -> gr.Blocks:
    auth.init_db()
    with gr.Blocks(title="AI Interview Coach") as demo:
        gr.HTML(f"<style>{LOADER_CSS}</style>")
        gr.Markdown("# AI Interview Coach\nPractice coaching only. Scores are estimates, not hiring decisions.")
        user = gr.State(None)
        state = gr.State({})

        with gr.Column() as auth_col:
            gr.Markdown("## Welcome\nSign in or create an account to practice.")
            with gr.Tabs():
                with gr.Tab("Sign in"):
                    si_email = gr.Textbox(label="Email")
                    si_pw = gr.Textbox(label="Password", type="password")
                    si_btn = gr.Button("Sign in", variant="primary")
                with gr.Tab("Create account"):
                    su_email = gr.Textbox(label="Email")
                    su_pw = gr.Textbox(label="Password (8 characters or more)", type="password")
                    su_confirm = gr.Textbox(label="Confirm password", type="password")
                    su_btn = gr.Button("Create account", variant="primary")

        with gr.Column(visible=False) as app_col:
            with gr.Row():
                who_md = gr.Markdown()
                signout_btn = gr.Button("Sign out", size="sm")
            with gr.Tabs():
                with gr.Tab("Interview"):
                    with gr.Row():
                        resume = gr.File(label="Resume (.pdf or .txt)", file_types=[".pdf", ".txt"], type="filepath")
                        job = gr.Textbox(label="Job description", lines=10)
                    start_btn = gr.Button("Start interview", variant="primary")
                    notes_md = gr.Markdown()

                    with gr.Column(visible=False) as interview_col:
                        question_md = gr.Markdown()
                        question_audio = gr.Audio(label="Question", type="filepath", interactive=False, autoplay=True)
                        mic = gr.Audio(label="Your answer", sources=["microphone"], type="filepath", format="wav")
                        transcribe_btn = gr.Button("Transcribe")
                        answer = gr.Textbox(label="Transcript (edit before submitting)", lines=6)
                        submit_btn = gr.Button("Submit answer")
                        feedback_md = gr.Markdown()

                    with gr.Column(visible=False) as report_col:
                        gr.Markdown("## Draft final report")
                        draft = gr.Textbox(label="Edit if needed", lines=18, interactive=True)
                        with gr.Row():
                            approve_btn = gr.Button("Approve final feedback", variant="primary")
                            reject_btn = gr.Button("Reject", variant="stop")
                        final_md = gr.Markdown()
                        download = gr.File(label="Download report (Markdown)", interactive=False, visible=False)
                        download_pdf = gr.File(label="Download report (PDF)", interactive=False, visible=False)
                        email_btn = gr.Button("Email me the PDF", visible=False)
                        email_md = gr.Markdown()

                with gr.Tab("Quiz"):
                    build_quiz_tab(state)

                with gr.Tab("Coding"):
                    coding_tab.build(user, state)

                with gr.Tab("My reports"):
                    refresh_btn = gr.Button("Refresh list")
                    report_pick = gr.Dropdown(label="Saved reports", choices=[], value=None)
                    report_view = gr.Markdown()

        auth_outputs = [user, auth_col, app_col, who_md, si_pw, su_pw, su_confirm]
        si_btn.click(sign_in, [si_email, si_pw], auth_outputs)
        su_btn.click(sign_up, [su_email, su_pw, su_confirm], auth_outputs)
        signout_btn.click(sign_out, None, [user, state, auth_col, app_col, who_md, interview_col, report_col])

        start_btn.click(
            start,
            [resume, job, state, user],
            [state, question_md, interview_col, feedback_md, report_col, final_md, download, notes_md, question_audio, answer, mic],
        )
        transcribe_btn.click(transcribe, [mic, state], [answer])
        submit_btn.click(
            submit,
            [answer, state],
            [state, question_md, answer, feedback_md, report_col, draft, question_audio, mic],
        )
        approve_btn.click(approve, [draft, state, user], [state, final_md, download, download_pdf, email_btn, email_md])
        reject_btn.click(reject, [state], [state, final_md, download, download_pdf, email_btn])
        email_btn.click(email_report, [state, user], [email_md])
        refresh_btn.click(refresh_reports, [user], [report_pick, report_view])
        report_pick.change(show_report, [report_pick, user], [report_view])
    return demo