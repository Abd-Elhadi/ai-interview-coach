# Code walkthrough (every member must be able to explain all of it)

## Data flow

1. ui/gradio_app.py: sign in or sign up. auth.py checks the password and the user goes into gr.State. Every action checks that state on the server.
2. The user uploads a resume and a job post. ui/backend.py reads the file (pdf or txt, 2 MB). input_guards.check_text cleans the text.
3. pipeline.start_session runs PlanningCrew with the seen question ids of the user. The planner calls the MCP tool get_interview_questions once per category. The tool returns a random sample of 3 and skips seen ids. The planner picks the best fit. valid_plan checks order, that source ids exist, and that they are unique. The ids are saved as seen.
4. The UI speaks the question with synthesize_question. The UI calls it in process.
5. The user records an answer. transcribe copies the audio to the audio folder and calls transcribe_answer. The file is deleted after use. The user edits and confirms the transcript.
6. pipeline.evaluate_answer cleans the answer and runs EvaluationCrew. The coach calls get_scoring_rubric and get_delivery_guidelines, reads its knowledge source, and sees a summary of earlier answers. valid_evaluation checks the output. Python then computes the weighted score, counts filler words, and removes an improved answer that contains numbers not in the answer.
7. After three answers, ReportCrew writes the narrative. The user edits, approves, or rejects it.
8. On approve, reporting.py writes Markdown and PDF, auth.save_report stores the report, and the user can email the PDF with emailer.py. My reports lists saved reports.
9. Quiz tab: quiz_pipeline runs MCQCrew from the job profile. quiz_guards checks the result. Scoring is plain Python.
10. Coding tab: coding_pipeline picks a random problem and removes hidden tests. runner.run_tests runs the code in a sandbox. Rejected code never reaches the LLM. CodeReviewCrew reviews the result. The suggested solution is re-run and shown only if it passes every test.

## File map

| File                                         | Purpose                                                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| config/agents.yaml, tasks.yaml               | Roles, goals, task prompts, context chain for interview agents                                   |
| config/quiz_agents.yaml, quiz_tasks.yaml     | Quiz writer and MCQ task                                                                         |
| config/coding_agents.yaml, coding_tasks.yaml | Code reviewer and review task                                                                    |
| schemas.py                                   | Pydantic output contracts and weighted_overall                                                   |
| crew.py                                      | Planning, Evaluation, Report, and CodeReview crews. MCP, knowledge, and guardrails attached here |
| crew_quiz.py                                 | MCQ crew                                                                                         |
| pipeline.py                                  | Interview orchestration and deterministic post-processing                                        |
| quiz_pipeline.py                             | MCQ generation and scoring                                                                       |
| coding_pipeline.py                           | Random problem, tests first, review second, verified suggestion                                  |
| knowledge.py                                 | Coach knowledge source                                                                           |
| rubrics.py                                   | Rubric weights and question bank ids                                                             |
| guardrails/input_guards.py                   | Length, injection lines, PII redaction                                                           |
| guardrails/output_guards.py                  | Validators for plan, evaluation, report, code review, invented numbers                           |
| guardrails/quiz_guards.py                    | Quiz validator                                                                                   |
| guardrails/tool_guards.py                    | Per-agent MCP tool allowlist                                                                     |
| mcp_server/server.py                         | Question bank, rubric, delivery, speech, coding tools                                            |
| mcp_server/data                              | questions.json, rubrics.json, delivery.json, coding_problems.json                                |
| coding/runner.py                             | Sandboxed test execution, language gating                                                        |
| auth.py                                      | Accounts, scrypt hashing, lockout, saved reports, seen questions                                 |
| reporting.py                                 | Markdown and PDF report builders                                                                 |
| emailer.py                                   | Resend call, recipient fixed to the account email, rate limit                                    |
| ui/gradio_app.py                             | Sign in gate, interview loop, report approval, My reports                                        |
| ui/quiz_tab.py, ui/coding_tab.py             | Quiz and coding tabs                                                                             |
| tests                                        | Schemas, guardrails, MCP tools, runner, coding pipeline, quiz, auth, email and PDF               |

## Questions to be ready for

1. Why separate crews? Different cadence: once, per answer, once, on request, per review.
2. Why output_pydantic? Typed, validated outputs the UI can render.
3. Why recompute the score in Python? Explainable and deterministic. The LLM only scores dimensions.
4. How does an agent call MCP? mcps=[MCPServerStdio(...)], a local subprocess over stdio.
5. How do you limit MCP tools? A tool_filter allowlist per agent plus server enums.
6. What happens when a guardrail fails? The error goes back to the agent and it retries up to 2 times.
7. Where is HITL? Edit and confirm the transcript before scoring. Then edit, approve, or reject the report.
8. How do you stop invented claims in improved answers? Placeholders in the prompt and a number check in code.
9. How is candidate code run safely? AST screening, isolated interpreter, empty environment, timeout. Not full isolation.
10. Why stdio and not HTTP for MCP? One process on the Space, no second deployment.
11. How do questions change between sessions? The MCP tool returns a random sample and skips the ids the user has seen. The ids are stored per user in SQLite.
12. How are passwords protected? scrypt with a random salt, constant-time compare, lockout after 5 failures.
13. How do you prevent hidden test leakage? Tests are removed from the problem before it reaches the UI or the prompt. The runner returns pass or fail for hidden cases.
14. Why is Python the only language on the Space? JavaScript and C# screening is substring based, and the Space has no node or dotnet.
15. Why does email go only to the account address? So the app cannot send mail to arbitrary people.
16. Where is MCP used by agents? The planner uses the question tool. The coach uses the rubric and delivery tools. Speech and coding tools live in the same server and are called by the UI and pipelines.
17. What does memory do? Earlier scores and gaps go into each evaluation, and seen question ids steer the next interview.
18. What does the knowledge source do? It gives the coach interview best practices so coaching stays consistent.
19. What happens if the LLM suggests a wrong solution? It is re-run in the sandbox and removed if any test fails.
20. What are the limits? Ephemeral Space disk, unverified emails, demo-grade sandbox, Resend test sender.
