import gradio as gr

from interview_coach import coding_pipeline

EDITOR_LANGUAGES = {"python": "python", "javascript": "javascript", "csharp": "c"}
LOADING_CSS = """
.coach-action-loading {
    opacity: 0.8;
    cursor: wait !important;
}
"""


def _button_loading(label: str):
    return gr.update(value=f"⏳ {label}...", interactive=False, elem_classes=["coach-action-loading"])


def _button_ready(label: str):
    return gr.update(value=label, interactive=True, elem_classes=[])


def _button_disabled(label: str):
    return gr.update(value=label, interactive=False, elem_classes=[])


def _problem_md(session: coding_pipeline.CodingSession) -> str:
    problem = session.problem
    return (
        f"## {problem['title']}\n\n{problem['prompt']}\n\n"
        f"**Language:** {coding_pipeline.LANGUAGE_DISPLAY[problem['language']]}  "
        f"**Difficulty:** {problem['difficulty']}  "
        f"**Function:** `{problem['function_name']}`"
    )


def _review_md(evaluation, reports: dict) -> str:
    submitted = reports["submitted"]
    suggested = reports["suggested"]
    lines = [
        f"### Submitted solution: {submitted['passed']} / {submitted['total']} tests passed",
        f"Correctness: {evaluation.correctness_score}/5 | Quality: {evaluation.quality_score}/5",
        f"**Complexity:** {evaluation.complexity_notes}",
    ]
    if submitted["error"]:
        lines.append(f"**Runner:** {submitted['error']}")
    if evaluation.feedback:
        lines.append("\n**Feedback**\n" + "\n".join(f"- {item}" for item in evaluation.feedback))
    if evaluation.improved_solution:
        lines.append(
            f"\n**Suggested solution verification:** {suggested['passed']} / {suggested['total']} tests passed"
        )
        fence_language = EDITOR_LANGUAGES[submitted.get("language", "python")]
        lines.append(f"\n```{fence_language}\n{evaluation.improved_solution}\n```")
    return "\n".join(lines)


def generate(language, difficulty):
    try:
        session = coding_pipeline.get_problem(difficulty, language)
    except Exception as err:
        raise gr.Error(f"Could not load a coding problem: {err}")
    return (
        session,
        _problem_md(session),
        gr.update(
            value=session.problem["starter_code"],
            language=EDITOR_LANGUAGES[session.problem["language"]],
        ),
        "",
        gr.update(value="", visible=False),
        _button_ready("Get problem"),
        _button_ready("Run tests and review"),
    )


def review(code, session):
    if session is None:
        raise gr.Error("Generate a coding problem first.")
    if not (code or "").strip():
        raise gr.Error("Enter a solution before reviewing it.")
    try:
        evaluation, reports = coding_pipeline.review_solution(session, code)
    except ValueError as err:
        raise gr.Error(str(err))
    except Exception as err:
        raise gr.Error(f"Code review failed: {err}")
    return _review_md(evaluation, reports), gr.update(value="", visible=False), _button_ready("Run tests and review")


def build() -> None:
    gr.HTML(f"<style>{LOADING_CSS}</style>")
    coding_state = gr.State(None)
    with gr.Row():
        language = gr.Dropdown(["Python", "JavaScript", "C#"], value="Python", label="Language")
        difficulty = gr.Dropdown(["easy", "medium", "hard"], value="easy", label="Difficulty")
        generate_btn = gr.Button("Get problem", variant="primary")
    problem_md = gr.Markdown()
    code = gr.Code(label="Your solution", language="python", lines=18)
    review_btn = gr.Button("Run tests and review", variant="primary", interactive=False)
    loading = gr.HTML(visible=False)
    result_md = gr.Markdown()
    generate_event = generate_btn.click(
        lambda: (_button_loading("Get problem"), gr.update(
            value='<div class="coach-loader"><span class="coach-loader-dot"></span><span>Loading a coding problem...</span></div>',
            visible=True,
        ), _button_disabled("Run tests and review")),
        outputs=[generate_btn, loading, review_btn],
    ).then(
        generate,
        [language, difficulty],
        [coding_state, problem_md, code, result_md, loading, generate_btn, review_btn],
    )
    generate_event.then(lambda: gr.update(value="", visible=False), outputs=loading)
    generate_event.failure(
        lambda: (
            _button_ready("Get problem"),
            gr.update(value="", visible=False),
            _button_disabled("Run tests and review"),
        ),
        outputs=[generate_btn, loading, review_btn],
    )
    review_event = review_btn.click(
        lambda: (_button_loading("Run tests and review"), gr.update(
            value='<div class="coach-loader"><span class="coach-loader-dot"></span><span>Running tests and reviewing your code...</span></div>',
            visible=True,
        )),
        outputs=[review_btn, loading],
    ).then(
        review,
        [code, coding_state],
        [result_md, loading, review_btn],
    )
    review_event.then(lambda: gr.update(value="", visible=False), outputs=loading)
    review_event.failure(
        lambda: (_button_ready("Run tests and review"), gr.update(value="", visible=False)),
        outputs=[review_btn, loading],
    )
