# Company configuration

This folder holds the assistant's **business profile**.

- `company.example.json` — a shipped **sample** profile (fictional Acme Growth Studio).
- `company.local.json.example` — a template for a real deployment.

To configure your own company, copy the template and edit it:

```bash
cp config/company.local.json.example config/company.local.json
```

`config/company.local.json` is **git-ignored** and overrides `company.example.json`.
Environment variables (`COMPANY_NAME`, `COMPANY_DOMAIN`, ...) override both.

Never put API keys or secrets here — those belong in `.env`. See
[../docs/company-configuration.md](../docs/company-configuration.md).
