---
title: AI Interview Coach
emoji: 🎤
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "6.30.0"
python_version: "3.12"
app_file: app.py
pinned: false
---

# AI Interview Coach

[Hugging Face Space](https://huggingface.co/spaces/abdelhadiOM/ai-interview-coach)

Multi-agent mock interview coach built with CrewAI and a custom MCP server.

## What it does

User provides a resume and job post. Agents analyze both and plan questions via an MCP
question bank. Each question is spoken with synthesize_question. The user records one
answer, the MCP tool transcribe_answer turns it into text, and the user edits and
confirms that transcript. Scoring uses only the confirmed text, against an MCP rubric.
The user approves the final report before it is finalized.

## Architecture

Input guardrails -> Job Analysis + Resume Analysis -> Interview Planner (MCP)
-> Question audio (synthesize_question) -> Record one answer -> transcribe_answer
-> Edit and confirm transcript -> Evaluator/Coach (MCP rubric) -> HITL approval
-> Final report.
See docs/architecture.md.

## Agents

| Agent             | Responsibility                              |
| ----------------- | ------------------------------------------- |
| Job Analysis      | Skills, duties, seniority, interview themes |
| Resume Analysis   | Experience and evidence                     |
| Interview Planner | Calls MCP for questions                     |
| Interviewer       | Asks one question, follow-ups               |
| Evaluator/Coach   | Calls MCP rubric, scores, coaches           |

## MCP server

Tools: get_interview_questions, get_scoring_rubric, get_delivery_guidelines, read_resume,
transcribe_answer, synthesize_question.
Question and rubric tools are read-only. Speech tools accept only files inside the audio directory.

## Guardrails

Input: file type/size, PII warning, prompt-injection filter.
Output: Pydantic schema, feedback must cite the answer.
Tool: enum validation, path restriction.

## Architecture

![AI-Intervew-Coach](assets/interview_coach_architecture_status.svg)

## HITL

Edit and confirm each transcript before it is scored. Edit, approve, or reject the final report.

## Features

- Sign up and sign in. Reports and seen questions are saved per account.
- Dynamic interviews: questions are sampled at random from a 24-question MCP bank, skip questions you already saw, and are tailored to your resume and the job.
- Voice: spoken questions, recorded answers, editable transcript before scoring.
- Rubric scoring with evidence, improved answers, and session memory across questions.
- Knowledge quiz generated from the job post.
- Coding session with random problems, sandboxed tests, and an AI code review. Python by default.
- Report: edit, approve, download as Markdown or PDF, email the PDF to your account address, and keep it under My reports.

## Configuration

| Variable                   | Purpose                                                            |
| -------------------------- | ------------------------------------------------------------------ |
| OPENAI_API_KEY             | Secret. LLM, speech                                                |
| MODEL                      | LLM name, default gpt-4o-mini                                      |
| RESEND_API_KEY, EMAIL_FROM | Email delivery                                                     |
| APP_DB_PATH                | SQLite path, default data/app.db                                   |
| ENABLED_LANGUAGES          | python (default). Add javascript, csharp only on a trusted machine |
| USE_KNOWLEDGE              | 0 disables the coach knowledge source                              |

## Known limits

- Space disk is not persistent, so accounts and saved reports reset when the Space restarts.
- Email addresses are not verified at sign up. Email goes only to the account address, 3 per hour.
- The code sandbox is demo-grade, not container isolation.
- The Resend test sender delivers only to the Resend account owner until a domain is verified.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
python app.py
```
