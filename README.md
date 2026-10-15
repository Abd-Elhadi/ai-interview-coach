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

Multi-agent mock interview coach built with CrewAI and a custom MCP server.

## What it does

User provides a resume and job post. Agents analyze both, plan questions via an MCP
question bank, run a practice interview, score each answer against an MCP rubric,
and produce coaching. The user approves the final report before it is finalized.

## Architecture

Input guardrails -> Job Analysis + Resume Analysis -> Interview Planner (MCP)
-> Interviewer -> Evaluator/Coach (MCP rubric) -> HITL approval -> Final report.
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

Tools: get_interview_questions, get_scoring_rubric, get_delivery_guidelines, read_resume.
All read-only, inputs validated against allowlists.

## Guardrails

Input: file type/size, PII warning, prompt-injection filter.
Output: Pydantic schema, feedback must cite the answer.
Tool: enum validation, path restriction.

## HITL

Transcript confirm/edit, final report approve/edit/reject.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
python app.py
```
