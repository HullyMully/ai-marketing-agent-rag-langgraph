# AI Customer Assistant

**Настраиваемый ИИ-ассистент для клиентов** для небольших компаний – на
**LangGraph**, **RAG (Qdrant)**, **FastAPI**, с **Telegram-ботом**, **мок-CRM**,
тикетами поддержки и эскалацией на человека. Настройте профиль бизнеса, загрузите
свою базу знаний, подключите LLM-провайдера и запускайте ассистента локально или
за собственным API.

> **В комплекте идёт вымышленная демонстрационная конфигурация** (digital-студия,
> только домены `.example`), поэтому проект работает «из коробки». Замените образцовый
> профиль компании и базу знаний на свои — см.
> [docs/company-configuration.ru.md](docs/company-configuration.ru.md).

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-stateful%20agent-orange)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

 [🇺🇸English](./README.md) | 🇷🇺Русский

---

## Скриншоты демо

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/landing-page.png" alt="Лендинг" width="100%"></td>
    <td width="50%"><img src="docs/screenshots/web-chat-lead-flow.png" alt="Создание лида" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><em>Лендинг</em></td>
    <td align="center"><em>Создание лида</em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/api-overview.png" alt="Обзор API" width="100%"></td>
    <td width="50%"><img src="docs/screenshots/metrics-dashboard.png" alt="Дашборд метрик" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><em>Обзор API</em></td>
    <td align="center"><em>Дашборд метрик</em></td>
  </tr>
</table>

Запустите API командой `uvicorn app.main:app --reload` и откройте локальное
веб-демо в браузере:

- Лендинг: <http://localhost:8000/>
- Веб-демо: <http://localhost:8000/demo>
- Обзор API: <http://localhost:8000/api-overview>
- Дашборд метрик: <http://localhost:8000/metrics>
- Swagger-документация: <http://localhost:8000/docs>

Ответы в веб-демо полностью генерирует живой агент (без скриптовых сценариев).
Подробнее – в [docs/web-demo.md](docs/web-demo.md), полный сценарий –
в [docs/demo/demo-walkthrough.md](docs/demo/demo-walkthrough.md). С агентом также
можно общаться через Telegram-бот.

## Что показывает проект

- Поток агента на LangGraph
- RAG по базе знаний маркетингового агентства
- Векторный поиск в Qdrant
- Бэкенд на FastAPI
- Интеграцию с Telegram-ботом
- CRM-действия и тикеты эскалации
- Память сессии и состояниевый диалог
- Многошаговую квалификацию лидов (спрашивает только недостающие поля, понимает уточнения)
- Естественную политику диалога: реагирует на приветствия, шутки, замешательство
  и раздражение, не повторяет один и тот же вопрос дважды и переключается в режим
  обсуждения (общие советы, без данных лида) — квалификация остаётся необязательной

Проект работает целиком без API-ключей (мок-LLM и эмбеддинги) либо с реальным
OpenAI-совместимым эндпоинтом при настройке.

---

## Зачем этот проект

Маркетинговые агентства получают множество повторяющихся входящих сообщений:
*«Что вы делаете?»*, *«Сколько стоит?»*, *«Как устроена кампания?»*, а также
реальных лидов и иногда жалобы, требующие участия человека. Этот проект –
**прототип для портфолио**, *реалистичный демо-сценарий*, **вдохновлённый типичными
рабочими процессами маркетинговых агентств**, который показывает, как небольшой
ИИ-агент может:

1. Отвечать на вопросы об **услугах** агентства (из базы знаний / RAG).
2. Объяснять **тарифные пакеты**.
3. **Квалифицировать** входящих лидов и собирать недостающие данные.
4. Создавать **лид** в мок-CRM.
5. Создавать **тикеты поддержки / эскалации**.
6. Отвечать на **внутренние** вопросы из базы знаний.
7. **Передавать** сложные случаи менеджеру-человеку.
8. Хранить **контекст разговора** между сообщениями.

Это намеренно **MVP**: чистый, читаемый код, ориентированный на демонстрацию
навыков, за которые нанимают Python AI Engineer уровня Junior/Middle.

## Ключевые возможности

- Бэкенд на **FastAPI** со схемами Pydantic и документацией Swagger.
- **LLM-планировщик диалога** как слой рассуждений: на каждое сообщение модель
  получает профиль компании, релевантные знания, историю, память, черновик лида,
  состояние тикета и доступные действия и возвращает одно структурированное
  JSON-решение (интент, режим, извлечённые поля, действие, ответ, источники,
  уверенность). Вывод **валидируется через Pydantic**, с одной починкой
  невалидного JSON.
- **Валидация действий на бэкенде**: планировщик только *рекомендует* — бэкенд
  решает, создавать ли лид или тикет, а ассистент подтверждает действие только
  после его выполнения бэкендом. Ответ `/chat` прозрачен об этом
  (`recommended_action`, `validation`, `action_executed`). Работает на небольшом
  конвейере **LangGraph** `plan → act`.
- **LangChain** для шаблонов промптов, абстракции LLM и retriever-цепочки.
- Поддержка **OpenAI-совместимых / DeepSeek** моделей и детерминированный режим `MOCK_LLM`.
- **RAG** по markdown-документамcle: чанкинг + эмбеддинги + векторный поиск в **Qdrant**.
- **Мок-CRM** + **тикеты**, сохраняемые в SQLite через чистый слой репозиториев.
- **Память сессии** – агент помнит данные (имя, контакт, услугу) в рамках сессии.
- **Telegram-бот** (aiogram), работающий через API.
- Эндпоинт **демо-метрик** (разговоры, лиды, тикеты, доли эскалации / решённых ИИ).
- **Docker Compose** (app + Qdrant, опц. бот), набор тестов **pytest**, документация.
- **Работает без единого API-ключа** в режиме `MOCK_LLM` + мок-эмбеддинги.

## Технологический стек

| Область | Выбор |
|---------|-------|
| Язык | Python 3.10+ |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Агент | LangGraph (граф состояний), LangChain |
| RAG | LangChain text splitters, Qdrant, OpenAI-совместимые или мок-эмбеддинги |
| Хранилище | SQLite + SQLAlchemy 2.0 (слой репозиториев) |
| Бот | aiogram 3 |
| Инфраструктура | Docker Compose, pytest, конфиги ruff/mypy |

## Архитектура

```mermaid
flowchart LR
    subgraph Clients
      U[Пользователь] --> TG[Telegram-бот<br/>aiogram]
      U --> SW[Swagger / curl]
    end
    TG -->|POST /chat| API[FastAPI Backend]
    SW -->|REST| API

    subgraph Backend
      API --> AG[LangGraph: plan -> act]
      AG --> PL[LLM-планировщик]
      PL --> LLM[(OpenAI-совместимый /<br/>DeepSeek, или мок)]
      AG --> MEM[(Память сессии)]
      AG --> RAG[RAG Retriever]
      AG --> TOOLS[Проверенные инструменты:<br/>CRM / Тикеты / Эскалация]
      RAG --> QD[(Qdrant<br/>Векторная БД)]
      TOOLS --> DB[(SQLite<br/>Лиды · Тикеты · Сообщения)]
      MEM --> DB
    end

    KB[knowledge_base/*.md] -->|ingest| QD
```

## Поток планировщика

```mermaid
stateDiagram-v2
    [*] --> plan
    plan --> act: структурированное решение (JSON)
    act --> create_lead: рекомендовано + правила бэкенда пройдены
    act --> create_ticket: эскалация обоснована
    act --> answer_from_knowledge: услуги / цены / процесс
    act --> ask_or_explore: приветствие / уточнение / обсуждение / пауза
    create_lead --> [*]
    create_ticket --> [*]
    answer_from_knowledge --> [*]
    ask_or_explore --> [*]
```

## Установка (локально, без Docker)

Нужен Python 3.10+.

```bash
git clone <url-вашего-форка> ai-marketing-agent-rag-langgraph
cd ai-marketing-agent-rag-langgraph

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # по умолчанию: MOCK_LLM=false
# затем задайте OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL

python scripts/ingest_knowledge.py   # индексация базы знаний
python scripts/seed_demo_data.py     # (опц.) демо-данные

uvicorn app.main:app --reload
```

Документация: **http://localhost:8000/docs**.

### Использование реального LLM

В `.env`:

```env
MOCK_LLM=false
USE_MOCK_EMBEDDINGS=false
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

## Запуск в Docker

```bash
# App + Qdrant (демо-режим, ключи не нужны). Индексация запускается автоматически.
docker compose up --build

# Дополнительно запустить Telegram-бот (нужен TELEGRAM_BOT_TOKEN)
docker compose --profile bot up --build
```

- API: http://localhost:8000/docs
- Дашборд Qdrant: http://localhost:6333/dashboard

## Настройка Telegram-бота

1. Создайте бота через [@BotFather](https://t.me/BotFather) и скопируйте токен.
2. Добавьте его в `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-ваш-токен
   API_BASE_URL=http://localhost:8000
   ```
3. Запустите API, затем бота:
   ```bash
   python -m bot.main
   ```
4. Напишите боту: `/start`, `/help` или любой вопрос.

Бот формирует стабильный `session_id` из id пользователя Telegram, поэтому память
работает по каждому пользователю. **Храните токен только в `.env` – не коммитьте его.**

## Примеры API

```bash
# Проверка здоровья
curl http://localhost:8000/health

# Чат: вопрос об услугах
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","user_message":"Какие услуги вы предлагаете?"}'

# Чат: стать лидом (два хода, один session_id -> память)
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","user_message":"I want to run Google Ads for my store."}'
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","user_message":"My name is Sam Carter, email sam@store.example."}'

# Создать лид напрямую
curl -X POST http://localhost:8000/crm/leads -H "Content-Type: application/json" \
  -d '{"name":"Jamie Lee","contact":"jamie@acme.example","service_interest":"SEO"}'

curl http://localhost:8000/tickets
curl http://localhost:8000/metrics/demo
```

| Метод | Путь | Назначение |
|-------|------|-----------|
| GET | `/health` | Проверка живости |
| POST | `/chat` | Диалог с агентом |
| POST | `/crm/leads` | Создать лид |
| GET | `/crm/leads` | Список лидов |
| POST | `/tickets` | Создать тикет |
| GET | `/tickets` | Список тикетов |
| GET | `/tickets/{id}` | Получить тикет |
| POST | `/knowledge/ingest` | Переиндексировать базу знаний |
| GET | `/metrics/demo` | Метрики рабочего пространства |

## Примеры диалогов

См. [docs/demo/demo-walkthrough.ru.md](docs/demo/demo-walkthrough.ru.md) – готовые
диалоги (услуги, цены, превращение в лида, эскалация, память). Чтобы прогнать полный
сценарий лида против запущенного сервера, используйте
`python scripts/test_production_flow.py`.

## Скриншоты

Добавляйте скриншоты в `docs/screenshots/` – см.
[docs/screenshots/README.md](docs/screenshots/README.md) (плейсхолдеры и промпт
для превью-изображения).

## Ограничения

См. [docs/limitations.md](docs/limitations.md): мок-LLM и
мок-эмбеддинги – детерминированные заглушки (не семантически сильные), нет
аутентификации, «CRM» – это локальная таблица SQLite, моделирующая паттерн
интеграции, а не реальный SaaS.

## Дорожная карта

См. [docs/roadmap.md](docs/roadmap.md): коннектор к реальной CRM, потоковые ответы,
аутентификация, харнесс для оценки качества, расширенная аналитика и др.

## Документация

- [Настройка компании](docs/company-configuration.ru.md) / [EN](docs/company-configuration.md)
- [Архитектура](docs/architecture.ru.md) / [EN](docs/architecture.md)
- [API](docs/api.ru.md) / [EN](docs/api.md)
- [RAG](docs/rag.ru.md) / [EN](docs/rag.md)
- [LangGraph flow](docs/langgraph-flow.ru.md) / [EN](docs/langgraph-flow.md)
- [Веб-демо](docs/web-demo.ru.md) / [EN](docs/web-demo.md)
- [Разбор демо](docs/demo/demo-walkthrough.ru.md) / [EN](docs/demo/demo-walkthrough.md)
- [Кейс для портфолио](docs/portfolio-case-study.ru.md) / [EN](docs/portfolio-case-study.md)
- [Ограничения](docs/limitations.ru.md) / [EN](docs/limitations.md)
- [Дорожная карта](docs/roadmap.ru.md) / [EN](docs/roadmap.md)
- [Скриншоты](docs/screenshots/README.ru.md) / [EN](docs/screenshots/README.md)

## Лицензия

MIT – см. [LICENSE](LICENSE). Все данные вымышленные/синтетические.
