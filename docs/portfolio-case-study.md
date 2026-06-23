# Portfolio case study – NovaGrowth AI Marketing Agent

🇺🇸English | [🇷🇺Русский](./portfolio-case-study.ru.md)

> **This is a fictional business case and a portfolio prototype.** "NovaGrowth
> Agency" is not a real company, and this work was **not** done for any real
> client. It is a *realistic demo scenario* **inspired by common marketing agency
> workflows**. All data is synthetic.

## The (fictional) problem

NovaGrowth Agency – a small, fictional digital marketing agency – receives many
repetitive messages from potential clients and internal team members: questions
about services, pricing and campaign workflow, plus genuine new leads and the
occasional complaint that needs a human. Handling these manually is slow and
inconsistent.

**Goal:** reduce manual work by using a conversational AI agent that can answer
from a knowledge base, qualify and capture leads automatically into a CRM, and
escalate complex cases to a human manager – while keeping conversation context.

## The prototype

A single FastAPI service exposing a LangGraph agent that:

- Answers **service / pricing / workflow** questions via **RAG** over a synthetic
  knowledge base.
- **Qualifies leads**: detects intent to work with the agency, collects missing
  details across turns, and creates a **CRM lead**.
- **Escalates**: routes explicit human requests, complaints, or low-confidence
  cases to a **support ticket** for a human manager.
- **Remembers** details within a session (name, contact, service interest).
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
