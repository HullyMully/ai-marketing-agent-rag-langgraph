# RAG (Retrieval-Augmented Generation)

[🇺🇸English](./rag.md) | 🇷🇺Русский

Агент отвечает на вопросы об услугах / ценах / процессах из небольшой markdown-базы
знаний, а не из параметрической памяти LLM. Релевантные чанки извлекаются и
передаются **LLM-планировщику** как `knowledge_context`; планировщик (или шаг
финального ответа) **обобщает** их в естественный ответ и записывает файлы-источники
в `sources`. Сырые чанки никогда не выгружаются пользователю.

## Пайплайн

```
knowledge_base/*.md
      │  загрузка (app/rag/loader.py)
      ▼
  Документы
      │  разбиение (app/rag/splitter.py – RecursiveCharacterTextSplitter, 700/120)
      ▼
   Чанки
      │  эмбеддинги (app/rag/embeddings.py)
      ▼
  Векторы ──► upsert ──► Qdrant (app/rag/vectorstore.py)
                              │  (in-memory запасной вариант, если Qdrant недоступен)
запрос ─► эмбеддинг ─► поиск top-k ─► чанки ─► промпт ─► ответ
```

## Компоненты

- **Loader** (`loader.py`): читает все файлы `*.md` в `knowledge_base/`.
- **Splitter** (`splitter.py`): LangChain `RecursiveCharacterTextSplitter`,
  `chunk_size=700`, `chunk_overlap=120`, разделители с учётом markdown.
- **Embeddings** (`embeddings.py`):
  - `OpenAIEmbeddingProvider` — реальные эмбеддинги через OpenAI-совместимый API.
  - `MockEmbeddingProvider` — детерминированный хеширующий «мешок слов» с фильтрацией
    стоп-слов. Семантически не сильный, но стабильный и без зависимостей, поэтому
    демо находит нужные документы без единого API-ключа.
- **Vector store** (`vectorstore.py`): `QdrantVectorStore` (основной) с
  запасным `InMemoryVectorStore` на косинусной близости.
- **Retriever** (`retriever.py`): синглтон на процесс, который эмбеддит запрос и
  возвращает top-k чанков с именами исходных файлов.

## Индексация

```bash
python scripts/ingest_knowledge.py
# или через эндпоинт
curl -X POST http://localhost:8000/knowledge/ingest
```

Скрипт/эндпоинт сообщает число документов и чанков, имя коллекции и
использованный режим эмбеддингов.

## Файлы базы знаний

`services.md`, `pricing.md`, `onboarding.md`, `campaign_workflow.md`, `faq.md`,
`escalation_policy.md`, `crm_policy.md` — всё это вымышленное образцовое содержимое
для digital-студии. Замените эти файлы своими документами и переиндексируйте базу.

## Замечания о демо-режиме

Мок-эмбеддинги нужны только для демонстрации. Для осмысленного семантического
поиска установите `USE_MOCK_EMBEDDINGS=false` и укажите ключ к API эмбеддингов.
Код пайплайна одинаков в обоих режимах — меняется только провайдер.
