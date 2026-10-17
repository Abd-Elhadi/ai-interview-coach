import gradio as gr

from interview_coach import quiz_pipeline

MAX_Q = 5


def generate(state):
    if not state or "session" not in state:
        raise gr.Error("Start the interview first so the quiz can use your job post.")
    try:
        mcqs = quiz_pipeline.generate_mcqs(state["session"], MAX_Q)
    except Exception as err:
        raise gr.Error(f"Could not generate the quiz: {err}")
    updates = []
    for i in range(MAX_Q):
        if i < len(mcqs.questions):
            q = mcqs.questions[i]
            updates.append(gr.update(label=f"{i + 1}. {q.question}", choices=q.options, value=None, visible=True))
        else:
            updates.append(gr.update(visible=False))
    return [mcqs, gr.update(visible=True), ""] + updates


def check(mcqs, p0, p1, p2, p3, p4):
    if mcqs is None or not getattr(mcqs, "questions", None):
        raise gr.Error("Generate the quiz first.")
    picks = []
    for q, choice in zip(mcqs.questions, [p0, p1, p2, p3, p4]):
        picks.append(q.options.index(choice) if choice in q.options else None)
    result = quiz_pipeline.score_mcqs(mcqs, picks)
    lines = [f"### Score {result['correct']} / {result['total']} ({result['ratio']:.0%})"]
    for i, (q, pick) in enumerate(zip(mcqs.questions, picks), 1):
        if pick != q.correct_index:
            lines.append(f"{i}. Correct answer: {q.options[q.correct_index]}. {q.explanation}")
    return "\n\n".join(lines)


def build(state):
    gr.Markdown("### Knowledge quiz\nQuestions are generated from the skills in your job post.")
    quiz_state = gr.State(None)
    gen_btn = gr.Button("Generate quiz", variant="primary")
    radios = [gr.Radio(choices=[], label="", visible=False) for _ in range(MAX_Q)]
    check_btn = gr.Button("Check answers", visible=False)
    result_md = gr.Markdown()
    gen_btn.click(generate, [state], [quiz_state, check_btn, result_md] + radios)
    check_btn.click(check, [quiz_state] + radios, [result_md])