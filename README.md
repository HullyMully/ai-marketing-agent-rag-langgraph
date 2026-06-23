# NovaGrowth AI Marketing Agent 

A conversational AI agent for a **fictional** digital marketing agency – built with
**LangGraph**, **RAG (Qdrant)**, **FastAPI**, a **Telegram bot**, a **mock CRM**,
support tickets and human escalation.

> **Portfolio case study for a fictional digital marketing agency. All demo data is fictional.**
> NovaGrowth Agency is not a real company, and this project is not affiliated with any real business.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-stateful%20agent-orange)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

🇺🇸English | [🇷🇺Русский](./README.ru.md)

---

## Demo screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/landing-page.png" alt="Landing page" width="100%"></td>
    <td width="50%"><img src="docs/screenshots/web-chat-lead-flow.png" alt="Lead creation flow" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><em>Landing page</em></td>
    <td align="center"><em>Lead creation flow</em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/api-overview.png" alt="API overview" width="100%"></td>
    <td width="50%"><img src="docs/screenshots/metrics-dashboard.png" alt="Metrics dashboard" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><em>API overview</em></td>
    <td align="center"><em>Metrics dashboard</em></td>
  </tr>
</table>

Run the API with `uvicorn app.main:app --reload`, then open the local web demo in
a browser:

- Landing page: <http://localhost:8000/>
- Web demo: <http://localhost:8000/demo>
- API overview: <http://localhost:8000/api-overview>
- Metrics dashboard: <http://localhost:8000/metrics>
- Swagger docs: <http://localhost:8000/docs>

See [docs/web-demo.md](docs/web-demo.md) for details, or
[docs/demo/demo-walkthrough.md](docs/demo/demo-walkthrough.md) for the full flow.
You can also talk to the agent through the Telegram bot.

## What this project demonstrates

- LangGraph-based agent flow
- RAG over a marketing agency knowledge base
- Qdrant vector search
- FastAPI backend
- Telegram bot integration
- CRM-style actions and escalation tickets
- Session memory and stateful dialogue

It runs end to end with no API keys (mock LLM and embeddings), or against a real
OpenAI-compatible endpoint when configured.

---

## Why this project exists

Marketing agencies field a flood of repetitive inbound messages: *"What do you do?"*,
*"How much is it?"*, *"How does a campaign work?"*, plus genuine leads and the
occasional complaint that needs a human. This project is a **portfolio prototype** –
a *realistic demo scenario* **inspired by common marketing agency workflows** – that
shows how a small AI agent can:

1. Answer questions about agency **services** (from a knowledge base / RAG).
2. Explain **pricing** packages.
3. **Qualify** incoming leads and collect missing details.
4. Create a **lead** in a mock CRM.
5. Create **support / escalation tickets**.
6. Answer **internal** questions from a knowledge base.
7. **Route** complex cases to a human manager.
8. Keep **conversation context** across messages.

It is intentionally an **MVP**: clean, readable, and focused on demonstrating the
skills a Junior/Middle Python AI Engineer is hired for – not a production system.

## Key features

- **FastAPI** backend with Pydantic schemas and Swagger docs.
- **LangGraph** stateful agent: `classify_intent > retrieve_knowledge >
  decide_action > {collect_missing_info | call_tool | generate_answer |
  escalate_to_human}`.
- **LangChain** for prompt templates, LLM abstraction and the retriever chain.
- **RAG** over markdown docs with chunking + embeddings + vector search in **Qdrant**.
- **Mock CRM** + **support tickets** persisted in SQLite via a clean repository layer.
- **Session memory** – the agent remembers details (name, contact, service) within a session.
- **Telegram bot** (aiogram) that talks to the API.
- **Demo metrics** endpoint (conversations, leads, tickets, escalation / resolved-by-AI rates).
- **Docker Compose** (app + Qdrant, optional bot), **pytest** suite, and thorough docs.
- **Runs with zero API keys** in `MOCK_LLM` + mock-embeddings demo mode.

## Tech stack

| Area | Choice |
|------|--------|
| Language | Python 3.10+ |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Agent | LangGraph (stateful graph), LangChain |
| RAG | LangChain text splitters, Qdrant vector DB, OpenAI-compatible or mock embeddings |
| Storage | SQLite + SQLAlchemy 2.0 (repository layer) |
| Bot | aiogram 3 |
| Tooling | Docker Compose, pytest, ruff/mypy configs |

## Architecture

```mermaid
flowchart LR
    subgraph Clients
      U[User] --> TG[Telegram Bot<br/>aiogram]
      U --> SW[Swagger / curl]
    end
    TG -->|POST /chat| API[FastAPI Backend]
    SW -->|REST| API

    subgraph Backend
      API --> AG[LangGraph Agent]
      AG --> MEM[(Session Memory)]
      AG --> RAG[RAG Retriever]
      AG --> TOOLS[Tools:<br/>CRM / Tickets / Escalation]
      RAG --> QD[(Qdrant<br/>Vector DB)]
      TOOLS --> DB[(SQLite<br/>Leads · Tickets · Messages)]
      MEM --> DB
    end

    KB[knowledge_base/*.md] -->|ingest| QD
```

## LangGraph flow

```mermaid
stateDiagram-v2
    [*] --> classify_intent
    classify_intent --> retrieve_knowledge
    retrieve_knowledge --> decide_action
    decide_action --> escalate_to_human: human / low confidence
    decide_action --> collect_missing_info: lead, missing info
    decide_action --> call_tool: lead, info complete
    decide_action --> generate_answer: service / pricing / workflow
    collect_missing_info --> [*]
    call_tool --> [*]
    escalate_to_human --> [*]
    generate_answer --> [*]
```

## Setup (local, no Docker)

Requires Python 3.10+.

```bash
# 1. Clone & enter
git clone <your-fork-url> ai-marketing-agent-rag-langgraph
cd ai-marketing-agent-rag-langgraph

# 2. Create a virtualenv and install
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure (demo mode works out of the box)
cp .env.example .env          # defaults: MOCK_LLM=true, mock embeddings

# 4. Ingest the knowledge base (uses in-memory store if Qdrant isn't running)
python scripts/ingest_knowledge.py

# 5. (optional) Seed synthetic demo leads/tickets
python scripts/seed_demo_data.py

# 6. Run the API
uvicorn app.main:app --reload
```

Open the interactive docs at **http://localhost:8000/docs**.

### Using a real LLM

Set the following in `.env` to use an OpenAI-compatible endpoint:

```env
MOCK_LLM=false
USE_MOCK_EMBEDDINGS=false
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

## Docker setup

```bash
# App + Qdrant (demo mode, no keys needed). Ingestion runs automatically.
docker compose up --build

# Also start the Telegram bot (needs TELEGRAM_BOT_TOKEN in your shell/.env)
docker compose --profile bot up --build
```

- API: http://localhost:8000/docs
- Qdrant dashboard: http://localhost:6333/dashboard

## Telegram bot setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Put it in `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-your-token
   API_BASE_URL=http://localhost:8000
   ```
3. Start the API, then run the bot:
   ```bash
   python -m bot.main
   ```
4. Message your bot: `/start`, `/help`, or just ask a question.

The bot derives a stable `session_id` from the Telegram user id, so memory works
per user. **Keep your token in `.env` only – never commit it.**

## API examples

```bash
# Health
curl http://localhost:8000/health

# Chat: ask about services
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","user_message":"What services do you offer?"}'

# Chat: become a lead (two turns, same session_id -> memory)
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","user_message":"I want to run Google Ads for my store."}'
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","user_message":"My name is Sam Carter, email sam@store.example."}'

# Create a lead directly
curl -X POST http://localhost:8000/crm/leads -H "Content-Type: application/json" \
  -d '{"name":"Jamie Lee","contact":"jamie@acme.example","service_interest":"SEO"}'

# Tickets & metrics
curl http://localhost:8000/tickets
curl http://localhost:8000/metrics/demo
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness probe |
| POST | `/chat` | Talk to the agent |
| POST | `/crm/leads` | Create a CRM lead |
| GET | `/crm/leads` | List leads |
| POST | `/tickets` | Create a ticket |
| GET | `/tickets` | List tickets |
| GET | `/tickets/{id}` | Get one ticket |
| POST | `/knowledge/ingest` | (Re)index the knowledge base |
| GET | `/metrics/demo` | Demo metrics |

## Demo scenarios

See [docs/demo-scenarios.md](docs/demo-scenarios.md) for five ready-to-run
conversations (services, pricing, becoming a lead, escalation, and memory).

## Screenshots

Add screenshots to `docs/screenshots/` – see
[docs/screenshots/README.md](docs/screenshots/README.md) for placeholders and a
social-preview image prompt.

## Limitations

This is a portfolio MVP. See [docs/limitations.md](docs/limitations.md) – highlights:
the mock LLM and mock embeddings are deterministic stand-ins (not semantically
strong), there is no auth, and the "CRM" is a local SQLite table modelling the
integration pattern rather than a real SaaS.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md): real CRM connector, streaming responses,
auth, evaluation harness, richer analytics dashboard, and more.

## Documentation

- [Architecture](docs/architecture.md) / [RU](docs/architecture.ru.md)
- [API](docs/api.md) / [RU](docs/api.ru.md)
- [RAG](docs/rag.md) / [RU](docs/rag.ru.md)
- [LangGraph flow](docs/langgraph-flow.md) / [RU](docs/langgraph-flow.ru.md)
- [Web demo](docs/web-demo.md) / [RU](docs/web-demo.ru.md)
- [Demo walkthrough](docs/demo/demo-walkthrough.md) / [RU](docs/demo/demo-walkthrough.ru.md)
- [Portfolio case study](docs/portfolio-case-study.md) / [RU](docs/portfolio-case-study.ru.md)
- [Limitations](docs/limitations.md) / [RU](docs/limitations.ru.md)
- [Roadmap](docs/roadmap.md) / [RU](docs/roadmap.ru.md)
- [Screenshots](docs/screenshots/README.md) / [RU](docs/screenshots/README.ru.md)

## License

MIT – see [LICENSE](LICENSE). All data is fictional/synthetic.
