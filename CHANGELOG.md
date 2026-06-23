# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/) and Semantic Versioning.

## [Unreleased]
### Changed
- Repositioned the project as a **configurable AI customer assistant platform**.
  The company identity (name, domain, description, contact, assistant name,
  escalation target, industry) is now loaded from `config/company.example.json`,
  an optional git-ignored `config/company.local.json`, and environment variables.
- Removed the hardcoded demo company from the product UI, agent and core code.
  The web UI shows the configured brand, generic suggested prompts and a real
  "Conversation state" panel driven by backend metadata.
- Knowledge base and sample data ship as a clearly-labelled fictional sample
  using `.example` domains; documents are meant to be replaced per deployment.

### Added
- `docs/company-configuration.md` (+ RU) describing how to configure a real
  company, replace the knowledge base and run ingestion.
- `scripts/test_production_flow.py` manual end-to-end check against a local server.

## [0.1.0] – 2026-06-22
### Added
- FastAPI backend: `/health`, `/chat`, `/crm/leads`, `/tickets`, `/knowledge/ingest`, `/metrics/demo`.
- LangGraph stateful agent with intent classification, RAG retrieval, action routing,
  lead collection, tool calls and human escalation.
- LangChain prompt templates and an LLM abstraction with a `MOCK_LLM` offline mode.
- RAG pipeline: markdown loader, recursive chunking, embeddings (OpenAI-compatible
  or deterministic mock) and Qdrant vector store with an in-memory fallback.
- Synthetic sample knowledge base for a fictional digital marketing studio.
- Mock CRM, support tickets and session memory backed by SQLite + a repository layer.
- Telegram bot (aiogram) talking to the API.
- Demo metrics endpoint.
- Docker Compose (app + Qdrant, optional bot), Dockerfile.
- pytest suite and full documentation set.
