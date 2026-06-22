# Web demo

A small browser UI for the agent, served by the same FastAPI app. It's handy for
trying the flows and for capturing screenshots.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                  # defaults to offline mode (no API keys)
python scripts/ingest_knowledge.py    # index the knowledge base
uvicorn app.main:app --reload
```

Then open:

- `http://localhost:8000/` — landing page
- `http://localhost:8000/demo` — chat demo
- `http://localhost:8000/docs` — API docs
- `http://localhost:8000/metrics/demo` — demo metrics (JSON)

The demo runs against the real `POST /chat` endpoint. The right-hand panel reads
back the created lead (`GET /crm/leads`), ticket (`GET /tickets/{id}`) and metrics
(`GET /metrics/demo`), so it shows actual backend data, not placeholders.

## Scenarios

The sidebar buttons each start a fresh session and run a short flow:

- **Services Q&A** — answered from the knowledge base (RAG)
- **Pricing from RAG** — pricing answered from the knowledge base
- **Lead creation flow** — captures a lead and shows the lead card
- **Human escalation** — opens a ticket and shows the ticket card
- **Memory follow-up** — two turns; the agent reuses details from the first

You can also type your own message. **Screenshot mode** (top-right) hides the
debug-style details and tightens the layout for clean captures.

## Suggested screenshots

Capture at 1440×900 (1600×900 also works):

1. **Landing page** — `/`
2. **Lead creation flow** — run the scenario, then turn on Screenshot mode
3. **Escalation flow** — run the scenario; the ticket card is visible
4. **API docs** — `/docs`
5. **Demo metrics** — the metrics card, or `/metrics/demo`

Keep tokens and any personal data out of frame. All demo data is fictional and
uses the `.example` domain.
