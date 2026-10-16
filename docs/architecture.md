# Architecture

```mermaid
flowchart TD
  UI[Gradio UI] --> IG[Input guardrails]
  IG --> PC[Planning crew]
  PC --> JA[Job Analysis agent]
  PC --> RA[Resume Analysis agent]
  JA --> PL[Interview Planner agent]
  RA --> PL
  PL -->|get_interview_questions| MCP[(Custom MCP server)]
  PL --> UI
  UI -->|confirmed answer| EC[Evaluation crew]
  EC -->|get_scoring_rubric, get_delivery_guidelines| MCP
  EC --> OG[Output guardrails and weighted score]
  OG --> UI
  UI --> RC[Report crew]
  RC --> HITL[HITL: edit, approve, reject]
  HITL --> DL[Download report]
```

## Guardrails

- Input: length limits, injection-line removal, email/phone/ID redaction.
- Output: plan order, rubric dimension match, evidence notes, no invented numbers.
- Tool: per-agent MCP tool allowlist, server-side enums, resume path guard, code runner sandbox.

## Planned

Coding session, speech in and out, email report, sign up and login, MCQs.
