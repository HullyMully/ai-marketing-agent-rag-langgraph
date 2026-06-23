# Справочник API

[🇺🇸English](./api.md) | 🇷🇺Русский

Интерактивная документация (Swagger UI): **http://localhost:8000/docs**
ReDoc: **http://localhost:8000/redoc**

## Эндпоинты

### `GET /health`
Проверка живости. Возвращает `{"status": "ok", "mock_llm": true}`.

### `POST /chat`
Общение с агентом.

Запрос:
```json
{ "session_id": "demo-1", "user_message": "How much is the Growth package?", "user_id": null }
```
Ответ:
```json
{
  "session_id": "demo-1",
  "answer": "...",
  "intent": "pricing_question",
  "escalated": false,
  "action_taken": "answered_from_kb",
  "created_lead_id": null,
  "created_ticket_id": null,
  "confidence": 0.95,
  "sources": ["pricing.md"]
}
```

### `POST /crm/leads`
Создать лид. Тело — `LeadCreate` (обязательны `name` и `contact`).

### `GET /crm/leads`
Список последних лидов (`LeadOut[]`).

### `POST /tickets`
Создать тикет поддержки / эскалации. Тело — `TicketCreate`.

### `GET /tickets` · `GET /tickets/{ticket_id}`
Список тикетов / получить один (404, если не найден).

### `POST /knowledge/ingest`
(Пере)индексировать markdown-базу знаний в векторное хранилище. Возвращает число
документов и чанков, а также режим эмбеддингов.

### `GET /metrics/demo`
Сводные демо-метрики:
```json
{ "conversations": 3, "leads": 4, "tickets": 2, "escalation_rate": 0.33, "resolved_by_ai_rate": 0.67 }
```

## Модели данных

**Lead**: `id, name, company, contact, service_interest, budget_range, message,
status, created_at`.

**Ticket**: `id, user_id, reason, summary, priority, status, created_at`.
