# Production Deploy

This project now has a production-oriented Docker Compose stack for a real
LLM-backed assistant:

- FastAPI app behind `uvicorn`
- PostgreSQL for leads, tickets, CRM dispatches and audit log
- Qdrant for vector search
- bind-mounted `knowledge_base/` and `config/` so admin edits survive container rebuilds
- optional Telegram bot profile

## 1. Prepare the server

Install Docker Engine and Docker Compose, clone the repository, then create a
production env file:

```bash
cp .env.production.example .env.production
```

Fill in at least:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `LLM_MODEL`
- `POSTGRES_PASSWORD`
- `DATABASE_URL` with the same Postgres password
- company profile fields

Keep `MOCK_LLM=false` and `USE_MOCK_EMBEDDINGS=false` for real customer traffic.

## 2. Start the stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

The app runs on `APP_PORT` (default `8000`). Put a reverse proxy such as Caddy,
Nginx or Traefik in front of it for TLS and a public domain.

## 3. Admin workflow

Open `/admin` after deploy:

- edit the company profile
- edit markdown knowledge-base files
- click `Re-index` after knowledge changes
- monitor leads, human inbox tickets, CRM dispatches and audit events

## 4. CRM sync

The local database is the source of truth. Outbound CRM sync is configured in
the admin panel:

- `local`: store leads only in this app
- `webhook`: POST each lead as JSON to a configured webhook URL
- `hubspot`, `pipedrive`, `google_sheets`: adapter placeholders; dispatch is
  recorded as skipped until a provider-specific adapter is implemented

Do not paste API keys into the admin panel. Put secrets in `.env.production` and
enter only the environment-variable name in `API key env var`.

## 5. Operational checklist

- Run the app behind HTTPS.
- Protect `/admin` and `/docs` with reverse-proxy auth or add application auth
  before exposing it publicly.
- Back up the Postgres volume and the bind-mounted `knowledge_base/` and `config/`.
- Review `/audit/events` regularly for profile, knowledge-base, lead, ticket and
  integration changes.
- Re-index knowledge after every document update.
- Keep `.env.production`, API keys and CRM tokens out of git.
