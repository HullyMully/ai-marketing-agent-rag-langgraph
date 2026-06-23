# Screenshots and visual assets

🇺🇸English | [🇷🇺Русский](./README.ru.md)

These visuals are demo assets for the portfolio case study. They use fictional
data only.

## Assets

Diagrams (`docs/assets/`):

- `social-preview.svg` – repository social-preview cover (1280×640)
- `architecture-overview.svg` – system architecture
- `langgraph-flow.svg` – agent state flow
- `rag-pipeline.svg` – RAG pipeline

Demo screenshots (`docs/screenshots/`):

- `landing-page.png` – landing page
- `web-chat-lead-flow.png` – lead creation flow in the chat demo
- `api-overview.png` – API overview page
- `metrics-dashboard.png` – metrics dashboard

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
