# Roadmap

🇺🇸English | [🇷🇺Русский](./roadmap.ru.md)

Possible next steps, roughly in priority order. This is a portfolio prototype, so
these are illustrative directions rather than commitments.

## Near term
- Swap the mock LLM/embeddings for a configured provider by default in a `prod` profile.
- Structured-output **LLM slot extraction** for lead qualification.
- **Streaming** chat responses (SSE / WebSocket).
- Persist session slot memory in the DB (survive restarts, multi-process safe).

## Mid term
- Real **CRM connector** (e.g., HubSpot/Pipedrive) behind the existing tools interface.
- **AuthN/AuthZ** (API keys / OAuth) and rate limiting.
- **Evaluation harness**: intent-classification accuracy, retrieval hit-rate, and
  answer-grounding checks in CI.
- Richer **analytics dashboard** (per-intent volumes, conversion funnel).

## Longer term
- Multi-language support (the bot already ships an EN/RU README).
- Human-handoff UI for managers to pick up escalations.
- Guardrails / PII redaction layer.
- Observability: tracing (LangSmith / OpenTelemetry) and metrics export.
