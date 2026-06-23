# RAG (Retrieval-Augmented Generation)

🇺🇸English | [🇷🇺Русский](./rag.ru.md)

The agent answers service / pricing / workflow questions from a small markdown
knowledge base rather than from the LLM's parametric memory.

## Pipeline

```
knowledge_base/*.md
      │  load (app/rag/loader.py)
      ▼
  Documents
      │  split (app/rag/splitter.py – RecursiveCharacterTextSplitter, 700/120)
      ▼
   Chunks
      │  embed (app/rag/embeddings.py)
      ▼
  Vectors ──► upsert ──► Qdrant (app/rag/vectorstore.py)
                              │  (in-memory fallback if Qdrant is down)
query ─► embed ─► search top-k ─► chunks ─► prompt ─► answer
```

## Components

- **Loader** (`loader.py`): reads every `*.md` file in `knowledge_base/`.
- **Splitter** (`splitter.py`): LangChain `RecursiveCharacterTextSplitter`,
  `chunk_size=700`, `chunk_overlap=120`, markdown-aware separators.
- **Embeddings** (`embeddings.py`):
  - `OpenAIEmbeddingProvider` – real embeddings via an OpenAI-compatible API.
  - `MockEmbeddingProvider` – deterministic hashing bag-of-words embedding with
    stopword filtering. Not semantically strong, but stable and dependency-free,
    so the demo retrieves the right documents without any API key.
- **Vector store** (`vectorstore.py`): `QdrantVectorStore` (primary) with an
  `InMemoryVectorStore` cosine fallback.
- **Retriever** (`retriever.py`): a process-wide singleton that embeds a query and
  returns the top-k chunks with their source file names.

## Ingestion

```bash
python scripts/ingest_knowledge.py
# or hit the endpoint
curl -X POST http://localhost:8000/knowledge/ingest
```

The endpoint/script reports the number of documents, chunks, the collection name
and which embedding mode was used.

## Knowledge base files

`services.md`, `pricing.md`, `onboarding.md`, `campaign_workflow.md`, `faq.md`,
`escalation_policy.md`, `crm_policy.md` – all synthetic content for the fictional
NovaGrowth Agency.

## Notes on demo mode

The mock embedding is for demonstration only. For meaningful semantic retrieval,
set `USE_MOCK_EMBEDDINGS=false` and provide an embeddings-capable API key. The
pipeline code is identical in both modes – only the provider changes.
