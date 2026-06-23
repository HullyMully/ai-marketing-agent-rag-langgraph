# Demo walkthrough

🇺🇸English | [🇷🇺Русский](./demo-walkthrough.ru.md)

Five end-to-end flows for the **AI Customer Assistant** (configured here with the
fictional sample profile). Everything runs
in offline mode (`MOCK_LLM=true`, mock embeddings), so no API keys are needed.

> Portfolio case study for a fictional agency. All demo data is fictional (`.example` domains).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest_knowledge.py        # index the knowledge base
uvicorn app.main:app --reload             # API at http://localhost:8000
# (optional) python scripts/seed_demo_data.py
```

Open Swagger at `http://localhost:8000/docs`, or use the `curl` calls below. Keep
the **same `session_id`** within a scenario to exercise conversation memory.

---

## Scenario 1 – Ask about services

**User message:** "What services do you offer?"

**Expected agent behavior:** classifies intent as `service_question`, retrieves
the relevant chunks from `services.md` via RAG, and returns a grounded answer with
`sources`. No lead or ticket is created.

**Related API / tool call:**
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s1","user_message":"What services do you offer?"}'
# > intent: service_question · sources: ["services.md", ...]
```

**Demo view:** `docs/screenshots/demo-chat.svg`,
`docs/assets/rag-pipeline.svg`

---

## Scenario 2 – Pricing question answered from RAG

**User message:** "How much does a campaign cost?"

**Expected agent behavior:** intent `pricing_question`; retrieves from `pricing.md`
and answers with package pricing. Demonstrates that answers are **grounded in the
knowledge base**, not invented.

**Related API / tool call:**
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s2","user_message":"How much does a campaign cost?"}'
# > intent: pricing_question · sources: ["pricing.md", ...]
```

**Demo view:** `docs/screenshots/demo-chat.svg`,
`docs/assets/rag-pipeline.svg`

---

## Scenario 3 – User becomes a lead

**User messages (same session):**
1. "I want to launch paid ads for my SaaS product."
2. "Around $5k/month. My name is Sam, company is BrightDesk, email sam@brightdesk.example."

**Expected agent behavior:** first message > intent `create_lead`, but required
fields are missing, so the agent asks a short follow-up (`collect_missing_info`).
Second message > the agent **remembers** the intent, extracts name + contact +
company + service + budget, and calls the `create_lead` tool. Response includes
`created_lead_id` and `action_taken: "created_lead"`.

**Related API / tool call:** `POST /chat` (twice) > internally calls the
`create_lead` CRM tool. Verify with:
```bash
curl localhost:8000/crm/leads
```

**Demo view:** `docs/screenshots/demo-chat.svg`,
`docs/screenshots/crm-lead-created.svg`

---

## Scenario 4 – Ask for a human > escalation

**User message:** "I need a custom enterprise plan – can I speak with a manager?"

**Expected agent behavior:** intent `human_escalation` (or low confidence) >
the agent creates a high-priority **escalation ticket** via the `escalate_to_human`
tool, sets `escalated: true`, and tells the user a manager will follow up.

**Related API / tool call:** `POST /chat` > `create_ticket` / `escalate_to_human`.
Verify with:
```bash
curl localhost:8000/tickets
```

**Demo view:** `docs/screenshots/escalation-ticket.svg`,
`docs/assets/langgraph-flow.svg`

---

## Scenario 5 – Check demo metrics

**Action:** after running the scenarios above, query aggregate metrics.

**Expected behavior:** returns conversation count, leads, tickets, escalation rate
and a resolved-by-AI rate computed from the SQLite data.

**Related API / tool call:**
```bash
curl localhost:8000/metrics/demo
# > {"conversations":..,"leads":..,"tickets":..,"escalation_rate":..,"resolved_by_ai_rate":..}
```

**Demo view:** `docs/screenshots/demo-metrics.svg`

---

## Summary of what each scenario proves

| Scenario | Skill demonstrated |
|----------|--------------------|
| 1 | RAG retrieval + grounded answers |
| 2 | Knowledge-base pricing answers (no hallucination) |
| 3 | Stateful dialogue, memory, lead qualification, CRM tool call |
| 4 | Escalation logic + human-in-the-loop ticketing |
| 5 | Metrics / observability over stored data |
