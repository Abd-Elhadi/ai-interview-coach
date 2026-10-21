# Architecture

Picture of the full flow: [assets/interview_coach_app_flow.svg](../assets/interview_coach_app_flow.svg)

## Interview flow

```mermaid
flowchart TD
  U["User in Gradio UI"] --> AUTH["Sign in or sign up (auth.py)"]
  AUTH --> DB[("SQLite: users, reports, seen questions")]
  AUTH --> IN["Resume and job post"]
  IN --> IG["Input guardrails: size, redact PII, drop injections"]
  IG --> PC["Planning crew: job, resume, planner"]
  PC -->|"get_interview_questions: random, skips seen ids"| MCP[("Custom MCP server, stdio")]
  PC --> OGP["Output guard: order, valid and unique source ids"]
  OGP --> Q["Question n of 3"]
  Q -.->|"synthesize_question, in process"| MCP
  Q --> REC["Record answer"]
  REC -.->|"transcribe_answer, in process, audio deleted"| MCP
  REC --> EDIT["HITL: edit and confirm transcript"]
  EDIT --> EC["Evaluation crew with knowledge and session history"]
  EC -->|"get_scoring_rubric, get_delivery_guidelines"| MCP
  EC --> OGE["Output guard, Python weighted score, invented number check"]
  OGE -->|"next question"| Q
  OGE -->|"all answered"| RC["Report crew"]
  RC --> HITL["HITL: edit, approve, reject"]
  HITL --> OUT["Markdown, PDF, My reports"]
  OUT --> DB
  OUT --> MAIL["Email via Resend to the account address"]
```

## Quiz and coding flows

```mermaid
flowchart LR
  JP["Job profile from the interview"] --> MQ["MCQ crew"]
  MQ --> QG["Quiz guard: unique, 4 distinct options"]
  QG --> QS["Python scoring"]
  P["Random problem, hidden tests removed"] --> ED["Code editor"]
  ED --> RUN["Sandbox runner: AST screen, timeout"]
  RUN -->|"rejected"| ERR["Show error, no LLM call"]
  RUN -->|"ran"| CR["Code review crew"]
  CR --> VER["Re-run suggested solution"]
  VER --> SHOW["Show results, keep suggestion only if all tests pass"]
```

## Crews

| Crew           | Runs               | Agents                                         | MCP tools                                         | Output                                   |
| -------------- | ------------------ | ---------------------------------------------- | ------------------------------------------------- | ---------------------------------------- |
| PlanningCrew   | once per interview | job analyst, resume analyst, interview planner | get_interview_questions                           | JobProfile, ResumeProfile, InterviewPlan |
| EvaluationCrew | once per answer    | evaluation coach                               | get_scoring_rubric, get_delivery_guidelines       | AnswerEvaluation                         |
| ReportCrew     | once at the end    | evaluation coach                               | none                                              | FinalReport                              |
| MCQCrew        | on request         | quiz writer                                    | none                                              | MCQSet                                   |
| CodeReviewCrew | per code review    | code reviewer                                  | none, it receives the visible tests in the prompt | CodeEvaluation                           |

The interviewer agent and the follow-up task are defined in the YAML files. The live flow does not call them yet.

## MCP server

One FastMCP server over stdio. Each agent sees only the tools it needs through a tool filter.

| Tool                               | Used by          | Notes                                                      |
| ---------------------------------- | ---------------- | ---------------------------------------------------------- |
| get_interview_questions            | planner agent    | random sample from a 24-question bank, skips excluded ids  |
| get_scoring_rubric                 | evaluation coach | weighted dimensions per question type                      |
| get_delivery_guidelines            | evaluation coach | time range and structure                                   |
| read_resume                        | available        | restricted upload folder                                   |
| synthesize_question                | UI, in process   | text to speech, capped at 600 characters, old files purged |
| transcribe_answer                  | UI, in process   | audio folder only, file deleted after use                  |
| get_coding_problem, get_test_cases | available        | hidden tests are never returned                            |

The speech functions live in the MCP server module and are exposed as MCP tools. The UI imports and calls them in process. Agents use the same server over stdio for questions and rubrics.

## Guardrails

- Input: length limits, injection-line removal, email, phone and ID redaction, resume file type and 2 MB limit.
- Output: plan order, source ids exist and are unique, rubric dimension match, evidence notes of 4 words or more, improved answer length, no invented numbers, complete report, valid quiz, valid code review.
- Tool: per-agent MCP allowlist, server-side enums, resume and audio path guards, code sandbox with AST screen, timeout and empty environment, hidden tests never exposed, suggested solutions re-run before display.
- Account: scrypt password hashing, lockout after 5 failures, reports read with an owner filter, email only to the account address, 3 per hour.

## Data stores

| Store                | Holds                                   | Lifetime                           |
| -------------------- | --------------------------------------- | ---------------------------------- |
| SQLite (APP_DB_PATH) | users, saved reports, seen question ids | resets when the Space restarts     |
| tmp/audio            | question audio and recordings           | purged after use or after one hour |
| gr.State             | current session, signed-in user         | per browser tab                    |

## Not done

Nothing planned for the demo. Limits are listed in the README.
