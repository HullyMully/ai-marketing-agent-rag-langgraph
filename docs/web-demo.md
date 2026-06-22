# Web demo

The project ships a small browser UI served by the FastAPI app — no build step,
just HTML, CSS and JavaScript.

## Run the app

```bash
pip install -r requirements.txt
cp .env.example .env            # demo mode works out of the box
python scripts/ingest_knowledge.py
uvicorn app.main:app --reload
```

## Open the pages

- Landing page: <http://localhost:8000/>
- Web chat demo: <http://localhost:8000/demo>
- API docs (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Demo metrics: <http://localhost:8000/metrics/demo>

The chat page generates a random `session_id` (kept in `localStorage`) and posts
to the existing `POST /chat` endpoint. The right panel shows the agent's intent,
action and any created lead or ticket id from the response.

## Demo scenarios

The left sidebar has one-click scenarios:

1. **Ask about services** — answered from the knowledge base (RAG).
2. **Ask about pricing** — pricing answered from the knowledge base.
3. **Create a lead** — provides name, company, budget and a `.example` contact;
   the agent qualifies and stores a lead.
4. **Ask for human manager** — triggers an escalation ticket.
5. **Follow-up with memory** — relies on earlier turns in the same session.

All demo data is fictional. Sample emails use the `.example` domain.

## Troubleshooting

- **`/` returns Not Found** — an older build is running. Restart with the latest
  code: `uvicorn app.main:app --reload`.
- **Chat fails or returns an error bubble** — confirm the API is healthy at
  `/health` and inspect `POST /chat` in `/docs`.
- **RAG answers look generic** — run knowledge ingestion:
  `python scripts/ingest_knowledge.py`.
