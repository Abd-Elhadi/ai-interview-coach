import gradio as gr

from interview_coach import coding_pipeline
from interview_coach.coding import runner

EDITOR_LANGUAGES = {"python": "python", "javascript": "javascript", "csharp": "c"}
LOADING = '<div class="coach-loader"><span class="coach-loader-dot"></span><span>{}</span></div>'


def _problem_md(session) -> str:
    problem = session.problem
    return (
        f"## {problem['title']}\n\n{problem['prompt']}\n\n"
        f"Language: {coding_pipeline.LANGUAGE_DISPLAY[problem['language']]} | "
        f"Difficulty: {problem['difficulty']} | Function: `{problem['function_name']}`"
    )


def _cell(value) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def _review_md(evaluation, reports: dict) -> str:
    submitted = reports["submitted"]
    if evaluation is None:
        return f"### Could not run your code\n\n{submitted['error']}"
    lines = [
        f"### Submitted solution: {submitted['passed']} / {submitted['total']} tests passed",
        f"Correctness {evaluation.correctness_score}/5 | Quality {evaluation.quality_score}/5",
        "",
        f"Complexity: {evaluation.complexity_notes}",
        "",
        "| Case | Result | Input | Expected | Got |",
        "|---|---|---|---|---|",
    ]
    for r in submitted["results"]:
        status = "pass" if r["passed"] else "fail"
        if r["visible"]:
            got = r["error"] if r.get("error") else r.get("got")
            lines.append(f"| {r['index'] + 1} | {status} | {_cell(r['args'])} | {_cell(r['expected'])} | {_cell(got)} |")
        else:
            lines.append(f"| {r['index'] + 1} | {status} | hidden | hidden | hidden |")
    if evaluation.feedback:
        lines += ["", "Feedback:"] + [f"- {item}" for item in evaluation.feedback]
    if evaluation.improved_solution:
        suggested = reports["suggested"]
        lines += ["", f"Suggested solution (verified {suggested['passed']} / {suggested['total']} tests):", ""]
        lines += [f"~~~{EDITOR_LANGUAGES[submitted['language']]}", evaluation.improved_solution, "~~~"]
    return "\n".join(lines)


def generate(language, difficulty, used, user):
    if not user:
        raise gr.Error("Sign in first.")
    try:
        session = coding_pipeline.get_problem(difficulty, language, exclude=used)
    except Exception as err:
        raise gr.Error(f"Could not load a coding problem: {err}")
    return (
        session,
        list(used) + [session.problem["id"]],
        _problem_md(session),
        gr.update(value=session.problem["starter_code"], language=EDITOR_LANGUAGES[session.problem["language"]]),
        "",
        gr.update(value="", visible=False),
    )


def review(code, session, user):
    if not user:
        raise gr.Error("Sign in first.")
    if session is None:
        raise gr.Error("Get a problem first.")
    if not (code or "").strip():
        raise gr.Error("Enter a solution before reviewing it.")
    try:
        evaluation, reports = coding_pipeline.review_solution(session, code)
    except ValueError as err:
        raise gr.Error(str(err))
    except Exception as err:
        raise gr.Error(f"Code review failed: {err}")
    return _review_md(evaluation, reports), gr.update(value="", visible=False)


def build(user) -> None:
    coding_state = gr.State(None)
    used_ids = gr.State([])
    choices = [coding_pipeline.LANGUAGE_DISPLAY[name] for name in runner.available_languages()]
    with gr.Row():
        language = gr.Dropdown(choices, value=choices[0], label="Language")
        difficulty = gr.Dropdown(["easy", "medium", "hard"], value="easy", label="Difficulty")
        generate_btn = gr.Button("Get problem", variant="primary")
    problem_md = gr.Markdown()
    code = gr.Code(label="Your solution", language="python", lines=18)
    review_btn = gr.Button("Run tests and review", variant="primary")
    loading = gr.HTML(visible=False)
    result_md = gr.Markdown()
    generate_btn.click(
        lambda: gr.update(value=LOADING.format("Loading a coding problem..."), visible=True),
        outputs=loading,
    ).then(
        generate,
        [language, difficulty, used_ids, user],
        [coding_state, used_ids, problem_md, code, result_md, loading],
    )
    review_btn.click(
        lambda: gr.update(value=LOADING.format("Running tests and reviewing your code..."), visible=True),
        outputs=loading,
    ).then(review, [code, coding_state, user], [result_md, loading])