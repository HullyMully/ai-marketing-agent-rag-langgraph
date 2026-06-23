# Разбор демо

[🇺🇸English](./demo-walkthrough.md) | 🇷🇺Русский

Пять сквозных сценариев для **AI Customer Assistant** (здесь — с вымышленным
образцовым профилем). Всё работает в
офлайн-режиме (`MOCK_LLM=true`, мок-эмбеддинги), поэтому API-ключи не нужны.

> Кейс для портфолио, вымышленное агентство. Все демо-данные вымышленные (домены `.example`).

## Подготовка

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest_knowledge.py        # индексация базы знаний
uvicorn app.main:app --reload             # API на http://localhost:8000
# (опц.) python scripts/seed_demo_data.py
```

Откройте Swagger на `http://localhost:8000/docs` или используйте `curl` ниже.
Сохраняйте **один `session_id`** в рамках сценария, чтобы задействовать память.

---

## Сценарий 1 — Вопрос об услугах

**Сообщение:** «What services do you offer?»

**Ожидаемое поведение:** интент классифицируется как `service_question`, через RAG
достаются релевантные чанки из `services.md`, возвращается обоснованный ответ с
`sources`. Лид или тикет не создаются.

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s1","user_message":"What services do you offer?"}'
# > intent: service_question · sources: ["services.md", ...]
```

**Демо-вид:** `docs/assets/rag-pipeline.svg`

---

## Сценарий 2 — Вопрос о ценах через RAG

**Сообщение:** «How much does a campaign cost?»

**Ожидаемое поведение:** интент `pricing_question`; ответ берётся из `pricing.md`.
Показывает, что ответы **обоснованы базой знаний**, а не выдуманы.

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s2","user_message":"How much does a campaign cost?"}'
# > intent: pricing_question · sources: ["pricing.md", ...]
```

**Демо-вид:** `docs/assets/rag-pipeline.svg`

---

## Сценарий 3 — Пользователь становится лидом

**Сообщения (одна сессия):**
1. «I want to launch paid ads for my SaaS product.»
2. «Around $5k/month. My name is Sam, company is BrightDesk, email sam@brightdesk.example.»

**Ожидаемое поведение:** первое сообщение → интент `create_lead`, но не хватает
обязательных полей, поэтому агент задаёт короткий уточняющий вопрос
(`collect_missing_info`). Второе сообщение → агент **помнит** намерение, извлекает
имя + контакт + компанию + услугу + бюджет и вызывает инструмент `create_lead`.
В ответе есть `created_lead_id` и `action_taken: "created_lead"`.

```bash
curl localhost:8000/crm/leads
```

**Демо-вид:** `docs/screenshots/web-chat-lead-flow.png`

---

## Сценарий 4 — Просьба о человеке → эскалация

**Сообщение:** «I need a custom enterprise plan – can I speak with a manager?»

**Ожидаемое поведение:** интент `human_escalation` (или низкая уверенность) → агент
создаёт **тикет эскалации** высокого приоритета через инструмент
`escalate_to_human`, выставляет `escalated: true` и сообщает, что менеджер свяжется.

```bash
curl localhost:8000/tickets
```

**Демо-вид:** `docs/assets/langgraph-flow.svg`

---

## Сценарий 5 — Проверка демо-метрик

**Действие:** после прогона сценариев выше запросите сводные метрики.

**Ожидаемое поведение:** возвращает число разговоров, лидов, тикетов, долю
эскалаций и долю решённых ИИ по данным из SQLite.

```bash
curl localhost:8000/metrics/demo
# > {"conversations":..,"leads":..,"tickets":..,"escalation_rate":..,"resolved_by_ai_rate":..}
```

**Демо-вид:** `docs/screenshots/metrics-dashboard.png`

---

## Что доказывает каждый сценарий

| Сценарий | Навык |
|----------|-------|
| 1 | RAG-поиск + обоснованные ответы |
| 2 | Цены из базы знаний (без галлюцинаций) |
| 3 | Состояниевый диалог, память, квалификация лида, вызов CRM-инструмента |
| 4 | Логика эскалации + тикеты с человеком в цикле |
| 5 | Метрики / наблюдаемость по сохранённым данным |
