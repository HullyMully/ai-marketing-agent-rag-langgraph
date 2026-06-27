# Demo walkthrough

🇺🇸English | [🇷🇺Русский](./demo-walkthrough.ru.md)

End-to-end flows for the **Configurable AI Customer Assistant Platform**,
configured here with the shipped sample profile (Acme Growth Studio). Everything
runs in offline mode (`MOCK_LLM=true`, mock embeddings), so no API keys are
needed. All demo data is fictional and uses `.example` domains.

In every flow the reply comes from the same pipeline: **LLM planner → backend
validation → final reply**. The deterministic offline engine follows the same
rules so the walkthrough is reproducible without a model.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest_knowledge.py        # index the knowledge base
uvicorn app.main:app --reload             # API at http://localhost:8000
# (optional) python scripts/seed_demo_data.py
```

Open the web UI at `http://localhost:8000/demo`, Swagger at `/docs`, or use the
`curl` calls below. Keep the **same `session_id`** within a scenario to exercise
conversation memory.

---

## Scenario 1 — Knowledge questions (RAG)

**User:** "What services do you provide?" then "What pricing packages are available?"

**Expected:** the planner answers from the knowledge base (RAG over `services.md`
/ `pricing.md`); `knowledge_used` is true and `sources` lists the files. The user
sees a natural, summarised answer — never raw chunks. No lead or ticket.

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s1","user_message":"What services do you provide?"}'
# > knowledge_used: true · sources: ["services.md", ...]
```

---

## Scenario 2 — Casual / meta / venting messages create nothing

**User (any of):** "Hello" · "SAY HELLO TO ME" · "Another one" ·
"What do you mean?" · "EXPLAIN WHAT DO YOU MEAN" · profanity.

**Expected:** a natural reply every time, **no lead, no ticket, no repeated menu,
no scripted fallback**. If the user stays confused or annoyed, qualification
pauses instead of pushing a form.

---

## Scenario 3 — Confused user, memory preserved

**User (same session):**
1. "Hello I need help with marketing"
2. "I don't know. Help me with that"
3. "Help starting a project please"
4. "I want paid ads for my SaaS"
5. "I don't remember"
6. "Oh sorry, company is FalkoTeam"
7. "FalkoTeam, I told you"

**Expected:** the assistant remembers **FalkoTeam** and the paid-ads/SaaS interest,
updates the lead draft, does **not** restart the flow or repeat the same question,
and does **not** create a lead (name/email/budget still missing) or a ticket.

---

## Scenario 4 — User becomes a lead

**User (same session):**
1. "I want to start a project"
2. "Paid ads for my SaaS"
3. "Company is BrightDesk, budget around $5k/month"
4. "My name is Sam, email sam@brightdesk.example"

**Expected:** no lead until the final message (required fields incomplete). After
message 4 the backend validates and creates **exactly one** lead containing
BrightDesk, Sam, `sam@brightdesk.example`, paid ads, SaaS and ~$5k/month. The
assistant confirms creation only **after** the backend confirms it; repeating the
details does not create a duplicate.

```bash
curl localhost:8000/crm/leads   # one lead for this session
```

**Screenshot:** `docs/screenshots/web-chat-lead-flow.png`

---

## Scenario 5 — Human escalation

**User:** "I need a human manager"

**Expected:** the backend creates a high-priority **escalation ticket** and the
assistant confirms hand-off — only **after** the ticket is created. The right
panel shows the real ticket; there is no fake ticket card beforehand.

```bash
curl localhost:8000/tickets
```

---

## Scenario 6 — Metrics

```bash
curl localhost:8000/metrics/demo
# > {"conversations":..,"leads":..,"tickets":..,"escalation_rate":..,"resolved_by_ai_rate":..}
```

**Screenshot:** `docs/screenshots/metrics-dashboard.png`

---

## What each scenario demonstrates

| Scenario | Demonstrates |
|----------|--------------|
| 1 | RAG retrieval + grounded answers with tracked sources |
| 2 | No lead/ticket on casual/meta/abusive input; no scripted fallback |
| 3 | Session memory + lead draft; no repeated questions |
| 4 | Validated, single lead creation only when all fields are present |
| 5 | Backend-confirmed escalation (no fake ticket cards) |
| 6 | Metrics / observability over stored data |
