# Web demo

🇺🇸English | [🇷🇺Русский](./web-demo.ru.md)

The FastAPI app serves a small dark-themed UI alongside the API. It shares one
design system across every page, so the landing, chat, API overview and metrics
all look like one internal product.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                  # defaults to offline mode (no API keys)
python scripts/ingest_knowledge.py    # index the knowledge base
uvicorn app.main:app --reload
```

## Pages

- `http://localhost:8000/` — landing page
- `http://localhost:8000/demo` — chat demo
- `http://localhost:8000/api-overview` — styled API overview (product view of the endpoints)
- `http://localhost:8000/metrics` — metrics dashboard (reads `/metrics/demo`)
- `http://localhost:8000/docs` — Swagger (unchanged)

## Chat demo

Every reply comes from the real assistant (`POST /chat`). The suggested-prompt
buttons just send a normal first message — you continue by typing. The assistant
handles **multi-turn lead qualification** with **session memory**: it remembers
what you've said, asks only for missing fields, handles corrections, and creates a
lead only once name, company, email, service and budget are known.

- **Services Q&A** / **Pricing from RAG** — answered from the knowledge base
- **Lead creation flow** — starts a multi-step qualification; reply with company,
  budget, name and email and the agent creates a CRM lead once it has them all
- **Human escalation** — opens a ticket for a manager
- **Memory follow-up** — the agent recalls details collected earlier in the session

The right-hand **Workflow result** panel shows the live session state: the lead
draft with its known and missing fields, a created lead or ticket, any knowledge
sources used, and whether session memory was used. A lead is shown as *created*
only once company, service, budget, name and email are all known.
