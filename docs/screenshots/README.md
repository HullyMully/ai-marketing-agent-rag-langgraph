# Screenshots and visual assets

These visuals are demo assets for the portfolio case study. They use fictional
data only.

## Assets

Diagrams (`docs/assets/`):

- `social-preview.svg` – repository social-preview cover (1280×640)
- `architecture-overview.svg` – system architecture
- `langgraph-flow.svg` – agent state flow
- `rag-pipeline.svg` – RAG pipeline

Demo views (`docs/screenshots/`):

- `demo-chat.svg` – conversational flow
- `crm-lead-created.svg` – lead creation in the CRM view
- `escalation-ticket.svg` – escalation ticket
- `demo-metrics.svg` – demo metrics
- `api-overview.svg` – API endpoints overview

## Notes

- No real customer data is used.
- Emails use the `.example` domain.
- Screenshots should not contain tokens, API keys or private data.

## Updating screenshots

To use captures from a running instance, start the app (`uvicorn app.main:app
--reload`), run the flows in [../demo/demo-walkthrough.md](../demo/demo-walkthrough.md),
and save PNGs into this folder. Then point the image paths in `README.md` and
`README.ru.md` at the new files. Capture at 1440×900 and keep tokens and personal
data out of frame.
