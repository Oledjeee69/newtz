# Dev Landing API

Backend-сервис для лендинга-презентации разработчика: REST API, форма обратной связи, AI-анализ, email-уведомления, rate limiting и логирование.

## Быстрый старт

```bash
cd dev-landing-api
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# заполните SMTP (Gmail App Password)
uvicorn app.main:app --reload --port 8000
```

- Лендинг: http://localhost:8000  
- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health  

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Email | aiosmtplib + Jinja2 (Gmail SMTP) |
| AI | **Groq / Gemini / OpenAI** + rule-based fallback |
| Хранение | JSON-файлы (логи, метрики, rate limit) |
| Деплой | Docker, Railway |
| Фронт | HTML/CSS/JS (в том же репо) |

## Архитектура

```
Routes → Services → Repositories
              ↓
         AI / SMTP
```

```
app/
  api/routes/       # HTTP-эндпоинты
  services/         # бизнес-логика
  repositories/     # файловое хранилище
  schemas/          # Pydantic DTO
  middleware/       # логирование запросов
  core/             # ошибки, handlers
frontend/           # лендинг + форма
templates/email/    # HTML-письма
data/               # логи, метрики (gitignore)
```

**Паттерны:** Service Layer, Repository, DTO, Graceful Degradation.

## API

### POST `/api/contact`

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Петров",
    "phone": "+7 999 123-45-67",
    "email": "ivan@example.com",
    "comment": "Интересует сотрудничество по backend-проекту"
  }'
```

**201 Created:**
```json
{
  "success": true,
  "message": "Обращение принято. Копия отправлена на ваш email.",
  "data": {
    "id": "cnt_abc123",
    "created_at": "2026-07-30T08:30:00+00:00",
    "ai": {
      "sentiment": "positive",
      "sentiment_score": 0.75,
      "request_type": "collaboration",
      "summary": "Запрос на сотрудничество...",
      "suggested_reply": "Здравствуйте...",
      "source": "fallback"
    }
  }
}
```

| Код | Описание |
|-----|----------|
| 201 | Успех |
| 422 | Ошибка валидации |
| 429 | Rate limit |
| 503 | SMTP недоступен |

### GET `/api/health`

Проверка статуса сервиса и конфигурации.

### GET `/api/metrics`

Статистика обращений. Опционально: заголовок `X-Metrics-Key`.

## AI-интеграция

**Цепочка провайдеров** (`AI_PROVIDER=auto`):

```
Groq → Gemini → OpenAI → rule-based fallback
```

Достаточно **одного бесплатного ключа**.

### Groq (рекомендуется, бесплатно)

1. Регистрация: [console.groq.com](https://console.groq.com)
2. API Keys → Create
3. В `.env`:

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
```

### Gemini (бесплатно)

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. В `.env`:

```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash
```

### OpenAI (платно, опционально)

```env
OPENAI_API_KEY=sk-proj-...
```

**Fallback:** если все провайдеры недоступны — rule-based классификатор (`source: "fallback"`).

Проверка: `GET /api/health` → `checks.ai_providers_available`.

## Безопасность

Self-pentest и исправления: см. [SECURITY.md](SECURITY.md)

Ключевые меры:
- Rate limit без обхода через `X-Forwarded-For` (локально)
- `TRUST_PROXY=true` только на Railway
- Санитизация email-заголовков от CRLF-injection
- `/api/metrics` закрыт в production
- Security headers, лимит размера body

## Промпт AI

Все провайдеры используют один промпт — анализ тональности, типа запроса, summary и suggested_reply в JSON.

## Gmail SMTP

1. Включите 2FA в Google-аккаунте
2. Создайте App Password: https://myaccount.google.com/apppasswords
3. В `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_FROM=your@gmail.com
OWNER_EMAIL=your@gmail.com
```

## Переменные окружения

См. `.env.example`.

| Переменная | Описание |
|------------|----------|
| `ALLOWED_ORIGINS` | CORS (добавьте Railway URL) |
| `TRUST_PROXY` | `true` на Railway, `false` локально |
| `GROQ_API_KEY` | Бесплатный AI (рекомендуется) |
| `GEMINI_API_KEY` | Бесплатный AI (альтернатива) |
| `OPENAI_API_KEY` | Платный AI (опционально) |
| `METRICS_API_KEY` | Обязателен в production |

## Хранение данных

| Данные | Путь |
|--------|------|
| Логи запросов | `data/logs/requests-YYYY-MM-DD.jsonl` |
| Логи ошибок | `data/logs/errors-YYYY-MM-DD.jsonl` |
| Метрики | `data/metrics.json` |
| Rate limit | `data/rate_limit/{ip_hash}.json` |

## Деплой на Railway

1. Push в GitHub
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Добавьте env vars из `.env.example`
4. `ALLOWED_ORIGINS` = `https://your-app.up.railway.app`
5. `TRUST_PROXY=true`
6. Health check: `/api/health`

```bash
# или локально через Docker
docker build -t dev-landing-api .
docker run -p 8000:8000 --env-file .env dev-landing-api
```

## Тесты

```bash
pytest -v
```

## Postman

Импортируйте `postman/dev-landing-api.postman_collection.json`.

## Что сделано с помощью AI

| С AI (Cursor) | Вручную |
|---------------|---------|
| Каркас проекта, boilerplate routes | Бизнес-логика ContactService |
| Черновик промпта OpenAI | Rule-based fallback |
| Примеры тестов | Rate limiting, формат логов |
| README-структура | Gmail SMTP, деплой Railway |

## Лицензия

MIT
