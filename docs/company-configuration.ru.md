# Настройка компании

[🇺🇸English](./company-configuration.md) | 🇷🇺Русский

В ассистент **не «зашита» никакая компания**. Это настраиваемая платформа: вы
задаёте профиль бизнеса и собственную базу знаний, и один и тот же код работает
для любой небольшой компании. Здесь описано, как настроить реальное развёртывание.

## Порядок приоритетов

Профиль бизнеса собирается из следующих источников по **возрастанию** приоритета
(побеждает более поздний):

1. **Встроенные запасные значения** — обобщённые безопасные значения по умолчанию
   (без реальной или демонстрационной компании).
2. **`config/company.example.json`** — поставляемый вымышленный образцовый профиль.
3. **`config/company.local.json`** — профиль вашего развёртывания (**в .gitignore**).
4. **Переменные окружения** — `COMPANY_NAME`, `COMPANY_DOMAIN`, … (высший приоритет).

То есть переменные окружения переопределяют локальный JSON, тот переопределяет
образцовый JSON, а он — запасные значения.

## Переменные окружения

Задайте их в `.env` (сначала скопируйте `.env.example`). Все они необязательны;
всё, что вы не зададите, берётся из JSON-конфига, а затем из безопасных значений.

| Переменная | Назначение | Пример |
|-----------|-----------|--------|
| `COMPANY_NAME` | Название/бренд в шапке UI и в диалоге | `Acme Growth Studio` |
| `COMPANY_DOMAIN` | Ваш домен (в образцах — только `.example`) | `acme.example` |
| `COMPANY_DESCRIPTION` | Описание в одно предложение | `Digital marketing and customer acquisition agency` |
| `COMPANY_CONTACT_EMAIL` | Публичный контактный адрес | `hello@acme.example` |
| `DEFAULT_ASSISTANT_NAME` | Отображаемое имя ассистента | `AI Assistant` |
| `DEFAULT_ESCALATION_TARGET` | Кому адресуется эскалация (в диалоге) | `human manager` |
| `BUSINESS_INDUSTRY` | Отрасль, для тона/контекста | `digital marketing` |

Пример фрагмента `.env`:

```env
COMPANY_NAME="Acme Growth Studio"
COMPANY_DOMAIN="acme.example"
COMPANY_DESCRIPTION="Digital marketing and customer acquisition agency"
COMPANY_CONTACT_EMAIL="hello@acme.example"
DEFAULT_ASSISTANT_NAME="AI Assistant"
DEFAULT_ESCALATION_TARGET="human manager"
BUSINESS_INDUSTRY="digital marketing"
```

## JSON-файлы конфигурации

- **`config/company.example.json`** — закоммиченный образец (вымышленная Acme
  Growth Studio). Считайте его документацией доступных полей; редактировать не нужно.
- **`config/company.local.json.example`** — шаблон для реального развёртывания.

Чтобы настроить реальную компанию, не трогая закоммиченный образец:

```bash
cp config/company.local.json.example config/company.local.json
# затем отредактируйте config/company.local.json
```

`config/company.local.json` находится в **.gitignore** и не будет закоммичен. Его
поля повторяют переменные окружения:

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

> Секреты никогда не хранятся в профиле компании. API-ключи и токены — только в
> `.env`, который в .gitignore.

## Замена базы знаний

Файлы в `knowledge_base/` — это **вымышленный образец** для digital-студии (только
домены `.example`). Замените их своими документами:

```
knowledge_base/
  services.md
  pricing.md
  faq.md
  onboarding.md
  escalation_policy.md
```

Любой файл `.md` в этой папке загружается, разбивается на чанки, эмбеддится и
становится доступным для поиска. Добавляйте, переименовывайте и удаляйте файлы
так, чтобы они соответствовали тому, что реально предлагает ваш бизнес.

## Запуск индексации

После редактирования базы знаний переиндексируйте её, чтобы ответы RAG отражали
ваш контент:

```bash
python scripts/ingest_knowledge.py
```

Скрипт загружает все `.md` из `knowledge_base/`, разбивает на чанки, эмбеддит и
записывает в векторное хранилище (Qdrant или in-memory, если Qdrant не запущен).
Переиндексацию можно запустить и через API:

```bash
curl -X POST http://localhost:8000/knowledge/ingest
```

## Подключение LLM-провайдера

По умолчанию проект работает в офлайн-моке (`MOCK_LLM=true`) без API-ключа. Чтобы
использовать реального OpenAI-совместимого провайдера (OpenAI, DeepSeek и т. д.),
задайте в `.env`:

```env
MOCK_LLM=false
USE_MOCK_EMBEDDINGS=false
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1   # DeepSeek: https://api.deepseek.com
LLM_MODEL=gpt-4o-mini                        # DeepSeek: deepseek-chat
EMBEDDING_MODEL=text-embedding-3-small
```

Критичные бизнес-действия (полнота обязательных полей лида, валидность email,
нужно ли создавать тикет, существует ли уже лид) проверяются **детерминированно**
в коде и никогда не зависят от LLM.

## Что НЕЛЬЗЯ коммитить

Держите вне системы контроля версий (уже добавлено в `.gitignore`):

- `.env` и любые файлы с API-ключами или токенами.
- `config/company.local.json` (профиль вашей реальной компании).
- Локальные базы данных (`*.db`, `*.sqlite`) и `qdrant_storage/`.
- Любые реальные клиентские или персональные данные. Образцовые данные должны
  оставаться вымышленными и использовать только домены `.example`.

## Проверка конфигурации

Запустите сервер и убедитесь, что шапка и ответы отражают вашу компанию:

```bash
uvicorn app.main:app --reload
# откройте http://localhost:8000/ и http://localhost:8000/demo
curl http://localhost:8000/config        # несекретный собранный профиль (JSON)
```

Эндпоинт `/config` возвращает только несекретные поля (он никогда не раскрывает
API-ключи).
