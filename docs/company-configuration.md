# Company configuration

🇺🇸English | [🇷🇺Русский](./company-configuration.ru.md)

The assistant ships with **no company baked in**. It is a configurable platform:
you supply a business profile and your own knowledge base, and the same code runs
for any small company. This page explains how to configure a real deployment.

## Resolution order

The business profile is resolved from the following sources, in **increasing**
priority (later wins):

1. **Built-in fallbacks** — generic, safe defaults (no real or demo company).
2. **`config/company.example.json`** — the shipped fictional sample profile.
3. **`config/company.local.json`** — your real deployment's profile (**git-ignored**).
4. **Environment variables** — `COMPANY_NAME`, `COMPANY_DOMAIN`, … (highest priority).

So environment variables override the local JSON, which overrides the example
JSON, which overrides the fallbacks.

## Environment variables

Set these in your `.env` (copy `.env.example` first). All are optional; anything
you leave unset falls back to the JSON config and then to the safe defaults.

| Variable | Purpose | Example |
|----------|---------|---------|
| `COMPANY_NAME` | Company / brand name shown in the UI header and used in conversation | `Acme Growth Studio` |
| `COMPANY_DOMAIN` | Your domain (use `.example` only in sample data) | `acme.example` |
| `COMPANY_DESCRIPTION` | One-sentence description of what you do | `Digital marketing and customer acquisition agency` |
| `COMPANY_CONTACT_EMAIL` | Public contact address | `hello@acme.example` |
| `DEFAULT_ASSISTANT_NAME` | Display name of the assistant | `AI Assistant` |
| `DEFAULT_ESCALATION_TARGET` | Who escalations are routed to, in conversation | `human manager` |
| `BUSINESS_INDUSTRY` | Industry, used for tone/context | `digital marketing` |

Example `.env` snippet:

```env
COMPANY_NAME="Acme Growth Studio"
COMPANY_DOMAIN="acme.example"
COMPANY_DESCRIPTION="Digital marketing and customer acquisition agency"
COMPANY_CONTACT_EMAIL="hello@acme.example"
DEFAULT_ASSISTANT_NAME="AI Assistant"
DEFAULT_ESCALATION_TARGET="human manager"
BUSINESS_INDUSTRY="digital marketing"
```

## JSON config files

- **`config/company.example.json`** — committed sample (fictional Acme Growth
  Studio). Treat it as documentation of the available fields; you don't have to
  edit it.
- **`config/company.local.json.example`** — a template for a real deployment.

To configure a real company without touching the committed sample:

```bash
cp config/company.local.json.example config/company.local.json
# then edit config/company.local.json
```

`config/company.local.json` is **git-ignored** and will not be committed. Its
fields mirror the environment variables:

```json
{
  "company_name": "Your Company",
  "company_domain": "your-domain.example",
  "company_description": "What your company does, in one sentence",
  "company_contact_email": "support@your-domain.example",
  "assistant_name": "AI Assistant",
  "escalation_target": "human manager",
  "business_industry": "your industry"
}
```

> Secrets never go in the company profile. API keys and tokens belong only in
> `.env`, which is git-ignored.

## Replace the knowledge base

The files in `knowledge_base/` are a **fictional sample** for a digital marketing
studio (all `.example` domains). Replace them with your own company documents:

```
knowledge_base/
  services.md
  pricing.md
  faq.md
  onboarding.md
  escalation_policy.md
```

Any `.md` file in this folder is loaded, chunked, embedded and made searchable.
Add, rename or remove files freely to match what your business actually offers.

## Run ingestion

After editing the knowledge base, re-index it so RAG answers reflect your content:

```bash
python scripts/ingest_knowledge.py
```

This loads every `.md` file in `knowledge_base/`, splits it into chunks, embeds
them, and writes them to the vector store (Qdrant, or an in-memory fallback when
Qdrant isn't running). You can also trigger a re-index over the API:

```bash
curl -X POST http://localhost:8000/knowledge/ingest
```

## Connect an LLM provider

By default the project is LLM-first (`MOCK_LLM=false`). To use a real
OpenAI-compatible provider (OpenAI, DeepSeek, etc.), set in `.env`:

```env
MOCK_LLM=false
USE_MOCK_EMBEDDINGS=false
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1   # DeepSeek: https://api.deepseek.com
LLM_MODEL=gpt-4o-mini                        # DeepSeek: deepseek-chat
EMBEDDING_MODEL=text-embedding-3-small
```

Critical business actions (whether required lead fields are complete, whether an
email is valid, whether a ticket should be created, whether a lead already exists)
are validated **deterministically** in code — they never depend on the LLM.

## What must NOT be committed

Keep these out of version control (they are already in `.gitignore`):

- `.env` and any file containing API keys or tokens.
- `config/company.local.json` (your real company profile).
- Local databases (`*.db`, `*.sqlite`) and `qdrant_storage/`.
- Any real customer or personal data. Sample data must stay fictional and use
  `.example` domains only.

## Verify your configuration

Start the server and confirm the header and answers reflect your company:

```bash
uvicorn app.main:app --reload
# open http://localhost:8000/ and http://localhost:8000/demo
curl http://localhost:8000/config        # non-secret resolved profile (JSON)
```

The `/config` endpoint returns only non-secret fields (it never exposes API keys).
