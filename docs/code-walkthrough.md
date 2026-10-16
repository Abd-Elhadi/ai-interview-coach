# Code walkthrough (every member must be able to explain all of it)

## Data flow

1. UI (gradio_app.py) loads the resume and calls pipeline.start_session.
2. input_guards.check_text cleans the text. PlanningCrew runs 3 tasks in sequence.
3. interview_planner calls the MCP tool get_interview_questions over stdio.
4. The user answers. pipeline.evaluate_answer runs EvaluationCrew.
5. evaluation_coach calls MCP get_scoring_rubric and get_delivery_guidelines.
6. Python recomputes the weighted score and checks the improved answer for invented numbers.
7. After 3 answers, ReportCrew writes the narrative. The user edits, approves, downloads.

## File map

| File                           | Purpose                                                       |
| ------------------------------ | ------------------------------------------------------------- |
| config/agents.yaml, tasks.yaml | Roles, goals, task prompts, context chain                     |
| schemas.py                     | Pydantic output contracts and weighted_overall                |
| crew.py                        | 3 crews, MCP attached per agent, guardrails attached per task |
| pipeline.py                    | Orchestration and deterministic post-processing               |
| guardrails/                    | Input cleaning, output validators, MCP tool allowlist         |
| mcp_server/server.py           | Question bank, rubric, delivery, coding tools                 |
| coding/runner.py               | Sandboxed test execution                                      |
| ui/gradio_app.py               | HITL gate, report download                                    |

## Questions to be ready for

1. Why 3 crews? Different cadence: once, per answer, once.
2. Why output_pydantic? Typed, validated outputs the UI can render.
3. Why recompute the score in Python? Explainable and deterministic. The LLM only scores dimensions.
4. How does an agent call MCP? mcps=[MCPServerStdio(...)], a local subprocess over stdio.
5. How do you limit MCP tools? tool_filter allowlist per agent plus server enums.
6. What happens when a guardrail fails? The error goes back to the agent and it retries up to 2 times.
7. Where is HITL? Report edit, approve, reject in the UI. Transcript confirm comes with speech.
8. How do you stop invented claims in improved answers? Placeholders in the prompt and a number check in code.
9. How is candidate code run safely? AST screening, isolated interpreter, empty env, timeout. Not full isolation.
10. Why stdio and not HTTP for MCP? One process on the Space, no second deployment.
