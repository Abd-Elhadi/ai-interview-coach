import gradio as gr

from interview_coach.ui import backend


def _question_md(state: dict) -> str:
    q = state["questions"][state["idx"]]
    n = state["idx"] + 1
    total = len(state["questions"])
    return f"### Question {n} of {total} ({q['category']})\n\n{q['question']}"


def _feedback_md(ev: dict) -> str:
    return (
        f"### Feedback, score {ev['overall_score']:.1f} / 5\n"
        f"Strengths: {'; '.join(ev['strengths'])}\n\n"
        f"Gaps: {'; '.join(ev['gaps'])}\n\n"
        f"Improve: {'; '.join(ev['improvements'])}"
    )


def start(resume_path, job_text, state):
    if not resume_path or not (job_text or "").strip():
        raise gr.Error("Upload a resume and paste a job description.")
    try:
        resume_text = backend.load_resume(resume_path)
    except ValueError as err:
        raise gr.Error(str(err))
    questions = backend.plan_interview(resume_text, job_text)
    state = {"questions": questions, "idx": 0, "evals": [], "approved": False}
    return (
        state,
        _question_md(state),
        gr.update(visible=True),
        "",
        gr.update(visible=False),
        "",
    )


def submit(answer, state):
    if not state or "questions" not in state:
        raise gr.Error("Start the interview first.")
    if len((answer or "").split()) < backend.MIN_ANSWER_WORDS:
        raise gr.Error(f"Answer needs at least {backend.MIN_ANSWER_WORDS} words.")
    question = state["questions"][state["idx"]]
    ev = backend.evaluate_answer(question, answer)
    state["evals"].append(ev)
    state["idx"] += 1
    if state["idx"] < len(state["questions"]):
        return state, _question_md(state), "", _feedback_md(ev), gr.update(visible=True), gr.update(visible=False), ""
    draft = backend.draft_report(state["evals"])
    return state, "### Interview complete", "", _feedback_md(ev), gr.update(visible=True), gr.update(visible=True), draft


def approve(draft_text, state):
    if not state or not state.get("evals"):
        raise gr.Error("Nothing to approve yet.")
    state["approved"] = True
    state["final_report"] = draft_text
    return state, "### Final report approved and saved for this session."


def reject(state):
    if state:
        state["approved"] = False
    return state, "### Report rejected. Edit the draft or click Start interview to run again."


def build_app() -> gr.Blocks:
    with gr.Blocks(title="AI Interview Coach") as demo:
        gr.Markdown(
            "# AI Interview Coach\n"
            "Practice coaching only. Scores are estimates, not hiring decisions."
        )
        state = gr.State({})
        with gr.Row():
            resume = gr.File(label="Resume (.pdf or .txt)", file_types=[".pdf", ".txt"], type="filepath")
            job = gr.Textbox(label="Job description", lines=10)
        start_btn = gr.Button("Start interview", variant="primary")

        with gr.Column(visible=False) as interview_col:
            question_md = gr.Markdown()
            answer = gr.Textbox(label="Your answer", lines=6)
            submit_btn = gr.Button("Submit answer")
            feedback_md = gr.Markdown()

        with gr.Column(visible=False) as report_col:
            gr.Markdown("## Draft final report")
            draft = gr.Textbox(label="Edit if needed", lines=16, interactive=True)
            with gr.Row():
                approve_btn = gr.Button("Approve final feedback", variant="primary")
                reject_btn = gr.Button("Reject", variant="stop")
            final_md = gr.Markdown()

        start_btn.click(
            start,
            [resume, job, state],
            [state, question_md, interview_col, feedback_md, report_col, final_md],
        )
        submit_btn.click(
            submit,
            [answer, state],
            [state, question_md, answer, feedback_md, interview_col, report_col, draft],
        )
        approve_btn.click(approve, [draft, state], [state, final_md])
        reject_btn.click(reject, [state], [state, final_md])
    return demo