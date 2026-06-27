# API reference

🇺🇸English | [🇷🇺Русский](./api.ru.md)

Interactive docs (Swagger UI): **http://localhost:8000/docs**
ReDoc: **http://localhost:8000/redoc**

## Endpoints

### `GET /health`
Liveness probe. Returns `{"status": "ok", "mock_llm": true}`.

### `GET /config`
Public, non-secret business profile used by the web UI (brand label, assistant
name, escalation target, …). No keys or secrets are ever returned.

### `POST /chat`
Talk to the agent. The agent is stateful — reuse the same `session_id` across
turns and it builds a lead draft, remembers details, and only creates a CRM lead
once the backend rules are satisfied.

Request:
```json
{ "session_id": "demo-1", "user_message": "How much is the Growth package?", "user_id": null }
```

Response (current schema, abbreviated):
```json
{
  "session_id": "demo-1",
  "answer": "Our Growth package is ... (natural, LLM-generated reply)",
  "intent": "pricing_question",
  "action": "answered_from_kb",
  "user_intent": "ask_pricing",
  "recommended_action": "answer_only",
  "knowledge_used": true,
  "sources": ["pricing.md"],
  "lead_draft": {},
  "missing_fields": ["name", "company", "contact_email", "service_interest", "budget_range"],
  "lead_created": false,
  "lead_id": null,
  "ticket_created": false,
  "ticket_id": null,
  "mode": "answering",
  "qualification_paused": false,
  "exploration_mode": false,
  "next_step": "...",
  "planner_decision": { "user_intent": "ask_pricing", "recommended_action": "answer_only", "...": "..." },
  "validation": { "allowed": null, "reason": "not_applicable", "missing_fields": [] },
  "action_executed": false,
  "memory_used": false,
  "confidence": 0.9,
  "escalated": false
}
```

The metadata is transparent about what happened: `recommended_action` is what the
planner proposed, `validation` is the backend's verdict (`allowed` + `reason` +
`missing_fields`), and `action_executed` says whether a lead/ticket was actually
created. `planner_decision` echoes the planner's structured output. Internal
prompts are never exposed.

### `POST /crm/leads`
Create a lead directly. Body → `LeadCreate` (`name` and `contact` required).

### `GET /crm/leads`
List recent leads (`LeadOut[]`).

### `POST /tickets`
Create a support / escalation ticket. Body → `TicketCreate`.

### `GET /tickets` · `GET /tickets/{ticket_id}`
List tickets / fetch one (404 if missing).

### `POST /knowledge/ingest`
(Re)index the markdown knowledge base into the vector store. Returns document /
chunk counts and the embedding mode.

### `GET /metrics/demo`
Aggregate workspace metrics computed from this instance's database:
```json
{ "conversations": 3, "leads": 4, "tickets": 2, "escalation_rate": 0.33, "resolved_by_ai_rate": 0.67 }
```

## The planner contract

For every `/chat` turn the **LLM planner** (`app/agent/planner.py`) receives a
single input bundle:

- `company_profile` — the configured business profile;
- `knowledge_context` — top-k RAG chunks (with sources);
- `recent_conversation_history`;
- `session_summary` and session memory;
- `lead_draft` — fields collected so far;
- `ticket_state`;
- `available_actions`;
- the latest `user_message`.

It returns one JSON object, validated with Pydantic (enums where it helps):

```json
{
  "user_intent": "greeting | casual_chat | ask_services | ask_pricing | ask_process | start_project | provide_lead_info | ask_human | complaint | meta_question | unclear",
  "assistant_mode": "answering | exploring | qualifying | paused | escalating | casual",
  "extracted_fields": {
    "name": null, "company": null, "email": null, "phone": null,
    "service_interest": null, "budget_range": null, "product_type": null,
    "budget_unknown": null, "user_agrees_to_proceed": null, "notes": null
  },
  "memory_updates": { "facts_to_remember": [], "lead_draft_updates": {} },
  "missing_fields": [],
  "recommended_action": "answer_only | update_lead_draft | create_lead | create_ticket | ask_clarifying_question | pause_qualification | retrieve_knowledge",
  "action_payload": {},
  "assistant_reply": "short natural reply",
  "knowledge_used": true,
  "sources": [],
  "confidence": 0.0,
  "safety_notes": []
}
```

Invalid JSON is repaired with one retry; a still-invalid result is handled as a
controlled internal error (never a crash, never a canned phrase).

## Action validation

The planner only recommends; `app/agent/validation.py` decides whether an action
runs.

**Lead** — created only when no lead exists for the session yet, and a name,
company, valid email and service interest are present, and a budget range is
present *or* the budget is explicitly unknown and the user agreed to proceed. No
duplicate leads per session.

**Ticket** — created only for an explicit human request, a real
complaint/frustration, a custom/enterprise need, or a high-confidence planner
escalation with a substantive reason. Greetings, "I am a new customer", ordinary
confusion, jokes and ordinary swearing never escalate.

If validation rejects an action, the assistant does **not** fake success — it
generates a natural reply (from the validation reason and missing fields) asking
for what's needed.

## Data models

**Lead**: `id, name, company, contact, service_interest, budget_range, message,
status, created_at`.

**Ticket**: `id, user_id, reason, summary, priority, status, created_at`.
