# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/) and Semantic Versioning.

## [0.1.0] – 2026-06-22
### Added
- FastAPI backend: `/health`, `/chat`, `/crm/leads`, `/tickets`, `/knowledge/ingest`, `/metrics/demo`.
- LangGraph stateful agent with intent classification, RAG retrieval, action routing,
  lead collection, tool calls and human escalation.
- LangChain prompt templates and an LLM abstraction with a `MOCK_LLM` offline mode.
- RAG pipeline: markdown loader, recursive chunking, embeddings (OpenAI-compatible
  or deterministic mock) and Qdrant vector store with an in-memory fallback.
- Synthetic knowledge base for the fictional "NovaGrowth Agency".
- Mock CRM, support tickets and session memory backed by SQLite + a repository layer.
- Telegram bot (aiogram) talking to the API.
- Demo metrics endpoint.
- Docker Compose (app + Qdrant, optional bot), Dockerfile.
- pytest suite and full documentation set.
