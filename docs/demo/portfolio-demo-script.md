# 90-second portfolio demo

English | [Русский](./portfolio-demo-script.ru.md)

Use this short path when presenting the project in an interview. Keep the demo
focused on engineering decisions rather than reading every feature from the UI.
All names and contacts below are fictional.

## Before the call

```bash
make setup
MOCK_LLM=true USE_MOCK_EMBEDDINGS=true make run
```

Optionally run `python scripts/seed_demo_data.py` once to populate the admin
workspace with synthetic leads and tickets.

## Walkthrough

**0–15 seconds — the problem**

“This is a configurable customer assistant. A company provides its profile and
documents; the assistant answers with RAG, remembers the conversation and can
recommend a lead or support action.”

**15–40 seconds — a validated action**

Open `/demo` and send:

> Please create a paid ads request for my SaaS. I am Sam Carter from BrightDesk,
> email sam@brightdesk.example, with a $5,000 per month budget.

Point to **Create lead**, **Approved** and **Action executed: Yes**. Explain that
the model recommends the action, while deterministic backend rules authorize it.

**40–65 seconds — operations**

Open `/admin`. Show the new lead and Human Inbox. Mention assignment, priority,
status and internal notes without editing every field during the presentation.

**65–80 seconds — configuration**

Show the markdown Knowledge Base Admin and CRM sync settings. Emphasize that
secrets are referenced through environment-variable names and are not stored in
the admin database.

**80–90 seconds — close**

“The project demonstrates FastAPI, LangGraph orchestration, RAG, validated side
effects, persistence, tests, CI and production-oriented Docker configuration.
Authentication and full multi-tenancy remain explicit future work.”
