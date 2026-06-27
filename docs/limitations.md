# Limitations

🇺🇸English | [🇷🇺Русский](./limitations.ru.md)

This project is a **portfolio MVP / prototype**, intentionally scoped to be clear
and runnable rather than production-grade. Known limitations:

## AI / RAG
- **Reasoning layer.** With a real OpenAI-compatible model the **LLM planner** is
  the reasoning layer (intent, memory, field extraction, reply strategy and the
  recommended action). With `MOCK_LLM=true` a deterministic engine reproduces the
  same decision contract offline — a predictable stand-in for tests/CI and a safe
  fallback, **not** a substitute for genuine LLM reasoning.
- **Mock embeddings** are a hashing bag-of-words with stopword filtering. They are
  stable and dependency-free but **not semantically strong**. Real embeddings give
  much better retrieval.
- **Deterministic field extraction** (email/budget/etc.) backs up the planner so
  business-critical fields stay reliable; it uses simple regexes and can miss
  unusual formats.
- **Action validation is deliberately deterministic** (`app/agent/validation.py`)
  so the LLM can never create a lead or ticket on its own — a safety feature, but
  it means the exact lead/ticket rules are code, not learned.

## Engineering
- **No authentication / rate limiting** on the API.
- **SQLite** single-file DB; fine for a demo, not for concurrent production load.
- **Session memory slots** are stored in-process (per running process); they reset
  on restart. Message history is persisted in SQLite.
- **Mock CRM**: leads are a local table modelling the integration pattern, not a
  real CRM (HubSpot/Pipedrive/etc.).
- **No streaming** responses; the agent returns a single message.
- **Minimal observability** (basic logging only).

## Data & safety
- All knowledge base content, leads, tickets and pricing are **synthetic**.
- No secrets are stored in the repo; tokens/keys live only in `.env`.

These are deliberate trade-offs to keep the project small, safe to publish, and
easy to run with zero API keys.
