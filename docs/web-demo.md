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
buttons just send a normal message — there are no scripted answers; you continue
by typing. Each turn is decided by the **LLM planner**, which reads the company
profile, relevant knowledge, recent history, session memory, the lead draft and
ticket state, then returns a structured decision. The **backend validates** that
decision before creating anything, so the assistant qualifies leads naturally,
handles greetings, jokes, confusion and frustration, and never forces a script.

- **Services Q&A** / **Pricing from RAG** — answered from the knowledge base
- **Lead creation flow** — the planner collects details across turns; the backend
  creates a CRM lead only once name, company, email, service and budget are known
- **Human escalation** — opens a ticket for a manager when escalation is justified
- **Memory follow-up** — the assistant recalls details collected earlier

The right-hand **Conversation state** panel shows the live planner output: the
current **mode** (answering / exploring / qualifying / paused), the detected
**intent**, **known interests**, the **lead draft** with its known and missing
fields, the **last action**, the **next suggested step**, and any **knowledge
sources** used. A lead is shown as *created* only once the backend actually
creates it — exploratory chats never display fake lead data.

## Real LLM

The demo is LLM-first by default (`MOCK_LLM=false`). Configure an
OpenAI-compatible endpoint — e.g. DeepSeek:

```bash
MOCK_LLM=false
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=...      # kept in the environment only; never logged or committed
LLM_MODEL=deepseek-chat
```
