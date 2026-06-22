# Limitations

This project is a **portfolio MVP / prototype**, intentionally scoped to be clear
and runnable rather than production-grade. Known limitations:

## AI / RAG
- **Mock LLM** (`MOCK_LLM=true`) is a deterministic, templated stand-in – it does
  not reason. Use a real OpenAI-compatible model for genuine generation.
- **Mock embeddings** are a hashing bag-of-words with stopword filtering. They are
  stable and dependency-free but **not semantically strong**. Real embeddings give
  much better retrieval.
- **Intent classification** in demo mode is keyword/rule-based. It is predictable
  and good for tests, but brittle on paraphrases; the LLM path is more robust.
- **Slot extraction** (name/contact/etc.) uses simple regexes and will miss
  unusual formats. Structured-output LLM extraction would be more reliable.

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
