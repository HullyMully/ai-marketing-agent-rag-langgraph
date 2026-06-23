# Web demo

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

The left sidebar has quick actions. Each one plays a clean, deterministic flow and
fills the right-hand **Workflow result** panel:

- **Lead creation flow** — qualifies a prospect and shows the lead card
- **Services Q&A** — answered from the knowledge base
- **Pricing from RAG** — pricing answered from the knowledge base
- **Human escalation** — opens a ticket and shows the ticket card
- **Memory follow-up** — the assistant reuses details from earlier in the session

Quick actions render a product-quality conversation and also call the backend
quietly, so leads, tickets and metrics stay real. Typing your own message runs a
live `POST /chat` and shows the actual answer.

## Suggested screenshots

Capture at 1440×900:

1. **Landing page** — `/`
2. **Lead creation flow** — run the quick action in `/demo`
3. **Escalation flow** — run the quick action in `/demo`
4. **API overview** — `/api-overview`
5. **Metrics dashboard** — `/metrics`

All demo data is fictional and uses the `.example` domain. Keep tokens and any
personal data out of frame.
