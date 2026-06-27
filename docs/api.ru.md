# Справочник API

[🇺🇸English](./api.md) | 🇷🇺Русский

Интерактивная документация (Swagger UI): **http://localhost:8000/docs**
ReDoc: **http://localhost:8000/redoc**

## Эндпоинты

### `GET /health`
Проверка живости. Возвращает `{"status": "ok", "mock_llm": true}`.

### `GET /config`
Публичный, несекретный профиль компании для веб-интерфейса (бренд, имя
ассистента, цель эскалации, …). Ключи и секреты никогда не возвращаются.

### `POST /chat`
Диалог с агентом. Агент сохраняет состояние — используйте один и тот же
`session_id` между сообщениями: он накапливает черновик лида, помнит детали и
создаёт лид в CRM только когда правила бэкенда выполнены.

Запрос:
```json
{ "session_id": "demo-1", "user_message": "Сколько стоит пакет Growth?", "user_id": null }
```

Ответ (текущая схема, сокращённо):
```json
{
  "session_id": "demo-1",
  "answer": "Наш пакет Growth ... (естественный ответ, сгенерированный LLM)",
  "intent": "pricing_question",
  "action": "answered_from_kb",
  "user_intent": "ask_pricing",
  "recommended_action": "answer_only",
  "knowledge_used": true,
  "sources": ["pricing.md"],
  "lead_draft": {},
  "missing_fields": ["name", "company", "contact_email", "service_interest", "budget_range"],
  "lead_created": false,
  "lead_id": null,
  "ticket_created": false,
  "ticket_id": null,
  "mode": "answering",
  "qualification_paused": false,
  "exploration_mode": false,
  "next_step": "...",
  "planner_decision": { "user_intent": "ask_pricing", "recommended_action": "answer_only", "...": "..." },
  "validation": { "allowed": null, "reason": "not_applicable", "missing_fields": [] },
  "action_executed": false,
  "memory_used": false,
  "confidence": 0.9,
  "escalated": false
}
```

Метаданные прозрачно показывают, что произошло: `recommended_action` — что
предложил планировщик, `validation` — вердикт бэкенда (`allowed` + `reason` +
`missing_fields`), `action_executed` — был ли реально создан лид/тикет.
`planner_decision` повторяет структурированный вывод планировщика. Внутренние
промпты никогда не раскрываются.

### `POST /crm/leads`
Создать лид напрямую. Тело → `LeadCreate` (`name` и `contact` обязательны).

### `GET /crm/leads`
Список недавних лидов (`LeadOut[]`).

### `POST /tickets`
Создать тикет поддержки / эскалации. Тело → `TicketCreate`.

### `GET /tickets` · `GET /tickets/{ticket_id}`
Список тикетов / получить один (404, если не найден).

### `POST /knowledge/ingest`
(Пере)индексировать markdown-базу знаний в векторное хранилище. Возвращает число
документов/чанков и режим эмбеддингов.

### `GET /metrics/demo`
Сводные метрики, вычисленные из базы данной инстанции:
```json
{ "conversations": 3, "leads": 4, "tickets": 2, "escalation_rate": 0.33, "resolved_by_ai_rate": 0.67 }
```

## Контракт планировщика

На каждом ходе `/chat` **LLM-планировщик** (`app/agent/planner.py`) получает единый
вход:

- `company_profile` — настроенный профиль компании;
- `knowledge_context` — top-k чанков из RAG (с источниками);
- `recent_conversation_history` — недавняя история;
- `session_summary` и память сессии;
- `lead_draft` — собранные поля;
- `ticket_state` — состояние тикета;
- `available_actions` — доступные действия;
- последнее `user_message`.

Он возвращает один JSON-объект, валидируемый через Pydantic (с enum, где это
полезно):

```json
{
  "user_intent": "greeting | casual_chat | ask_services | ask_pricing | ask_process | start_project | provide_lead_info | ask_human | complaint | meta_question | unclear",
  "assistant_mode": "answering | exploring | qualifying | paused | escalating | casual",
  "extracted_fields": {
    "name": null, "company": null, "email": null, "phone": null,
    "service_interest": null, "budget_range": null, "product_type": null,
    "budget_unknown": null, "user_agrees_to_proceed": null, "notes": null
  },
  "memory_updates": { "facts_to_remember": [], "lead_draft_updates": {} },
  "missing_fields": [],
  "recommended_action": "answer_only | update_lead_draft | create_lead | create_ticket | ask_clarifying_question | pause_qualification | retrieve_knowledge",
  "action_payload": {},
  "assistant_reply": "короткий естественный ответ",
  "knowledge_used": true,
  "sources": [],
  "confidence": 0.0,
  "safety_notes": []
}
```

Невалидный JSON чинится одной повторной попыткой; по-прежнему некорректный
результат обрабатывается как контролируемая внутренняя ошибка (никаких падений и
шаблонных фраз).

## Валидация действий

Планировщик только рекомендует; `app/agent/validation.py` решает, выполнять ли
действие.

**Лид** — создаётся, только если для сессии ещё нет лида и присутствуют имя,
компания, валидный email и интерес к услуге, и указан бюджет *или* бюджет явно
неизвестен, а пользователь согласился продолжить. Дубликаты лидов на сессию
запрещены.

**Тикет** — создаётся только при явном запросе человека, реальной
жалобе/раздражении, кастомной/корпоративной потребности или высоконадёжной
эскалации планировщика с содержательной причиной. Приветствия, «я новый клиент»,
обычная растерянность, шутки и обычная брань никогда не эскалируют.

Если валидация отклоняет действие, ассистент **не** имитирует успех — он
генерирует естественный ответ (из причины отказа и недостающих полей) с просьбой
дать необходимое.

## Модели данных

**Lead**: `id, name, company, contact, service_interest, budget_range, message,
status, created_at`.

**Ticket**: `id, user_id, reason, summary, priority, status, created_at`.
