# Example case study – AI Customer Assistant

🇺🇸English | [🇷🇺Русский](./portfolio-case-study.ru.md)

> **This is a worked example using the shipped fictional sample company.**
> "Acme Growth Studio" is not a real company; it is the sample profile bundled with
> the platform to show how a small business would configure and use the assistant.
> All data is fictional and uses `.example` domains.

## The (fictional) problem

Acme Growth Studio – a small, fictional digital marketing agency – receives many
repetitive messages from potential clients and internal team members: questions
about services, pricing and campaign workflow, plus genuine new leads and the
occasional complaint that needs a human. Handling these manually is slow and
inconsistent.

**Goal:** reduce manual work by using a conversational AI agent that can answer
from a knowledge base, qualify and capture leads automatically into a CRM, and
escalate complex cases to a human manager – while keeping conversation context.

## The prototype

A single FastAPI service exposing a LangGraph agent whose reasoning layer is an
**LLM planner** with **backend action validation**:

- The **planner** reads the company profile, RAG knowledge, history, session
  memory, the lead draft and ticket state, and returns one structured JSON
  decision: intent, memory updates, extracted fields, reply strategy and a single
  recommended action.
- The **backend validates every action** and creates a **CRM lead** or
  **escalation ticket** only when its deterministic rules allow — the LLM never
  creates records on its own, and the assistant confirms an action only after the
  backend executes it.
- Answers **service / pricing / workflow** questions via **RAG** over a synthetic
  knowledge base, with sources tracked in the response.
- **Remembers** details within a session (name, company, contact, service
  interest); the final user-facing reply is **LLM-generated**, not scripted.
- Is reachable via REST and a **Telegram bot**.

## Why these technologies

| Requirement | Implementation | Why |
|-------------|----------------|-----|
| Conversational, stateful logic | **LangGraph** state machine | Explicit, inspectable dialogue flow |
| Prompting / LLM abstraction | **LangChain** | Standard building blocks; easy LLM swap |
| Answer from documents | **RAG** + **Qdrant** | Grounded answers, no hallucinated pricing |
| CRM-like actions | Tools + **SQLite** repositories | Models a real integration without a SaaS |
| Escalation | High-priority tickets | Clear human-in-the-loop handoff |
| Reach | **FastAPI** + **aiogram** bot | Realistic multi-channel surface |
| Reproducibility | **Docker Compose**, **pytest**, mock modes | Runs anywhere, no keys required |

## What this demonstrates (for a Python AI Engineer role)

Python, FastAPI, LangChain, LangGraph, RAG, a vector database, conversational AI,
stateful dialogue logic, memory, API integrations, CRM-like actions, escalation
logic, a Telegram bot, Docker Compose, tests, and clear documentation.

## Results (illustrative demo metrics)

The `/metrics/demo` endpoint computes conversation count, leads, tickets,
escalation rate and a resolved-by-AI rate from the SQLite data – the kind of
KPI surface an agency would care about. Numbers depend on the conversations you run.

## Honest framing

This is an **MVP portfolio prototype**, not a production deployment. See
[limitations.md](limitations.md) and [roadmap.md](roadmap.md) for what is
intentionally simplified and what would come next.
