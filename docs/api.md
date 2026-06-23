# API reference

🇺🇸English | [🇷🇺Русский](./api.ru.md)

Interactive docs (Swagger UI): **http://localhost:8000/docs**
ReDoc: **http://localhost:8000/redoc**

## Endpoints

### `GET /health`
Liveness probe. Returns `{"status": "ok", "mock_llm": true}`.

### `POST /chat`
Talk to the agent.

Request:
```json
{ "session_id": "demo-1", "user_message": "How much is the Growth package?", "user_id": null }
```
Response:
```json
{
  "session_id": "demo-1",
  "answer": "...",
  "intent": "pricing_question",
  "escalated": false,
  "action_taken": "answered_from_kb",
  "created_lead_id": null,
  "created_ticket_id": null,
  "confidence": 0.95,
  "sources": ["pricing.md"]
}
```

### `POST /crm/leads`
Create a lead. Body > `LeadCreate` (`name` and `contact` required).

### `GET /crm/leads`
List recent leads (`LeadOut[]`).

### `POST /tickets`
Create a support / escalation ticket. Body > `TicketCreate`.

### `GET /tickets` · `GET /tickets/{ticket_id}`
List tickets / fetch one (404 if missing).

### `POST /knowledge/ingest`
(Re)index the markdown knowledge base into the vector store. Returns document /
chunk counts and the embedding mode.

### `GET /metrics/demo`
Aggregate demo metrics:
```json
{ "conversations": 3, "leads": 4, "tickets": 2, "escalation_rate": 0.33, "resolved_by_ai_rate": 0.67 }
```

## Data models

**Lead**: `id, name, company, contact, service_interest, budget_range, message,
status, created_at`.

**Ticket**: `id, user_id, reason, summary, priority, status, created_at`.
