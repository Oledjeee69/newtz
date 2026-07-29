# Contact API — backend для лендинга разработчика

REST API для формы обратной связи: валидация → AI-анализ комментария → email → ответ клиенту.  
Рядом — статичный лендинг с формой для демо.

**Демо:** https://newtz-production.up.railway.app  
**Swagger:** https://newtz-production.up.railway.app/docs  
**Репозиторий:** https://github.com/Oledjeee69/newtz

---

## 1. Как запустить проект

### Требования

- Python 3.11+
- pip

### Установка зависимостей

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируй `.env`. Минимум для локального запуска:

| Переменная | Назначение |
|---|---|
| `OWNER_EMAIL` | Куда слать заявки |
| `SMTP_*` | Gmail App Password для локальной отправки |
| `GEMINI_API_KEY` или `GROQ_API_KEY` | AI (опционально — есть fallback) |

Полный список — в `.env.example`.

### Запуск

```bash
uvicorn app.main:app --reload --port 8000
```

- Лендинг с формой: http://localhost:8000  
- OpenAPI (Swagger): http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  

### Тесты

```bash
pytest -v
```

### Docker

```bash
docker build -t contact-api .
docker run -p 8000:8000 --env-file .env contact-api
```

### Деплой на Railway

В репозитории есть `Dockerfile` и `railway.toml` (healthcheck `/api/health`).

```bash
railway up
```

**Переменные для production (Railway):**

```env
DEBUG=false
TRUST_PROXY=true
DATA_DIR=/app/data
ALLOWED_ORIGINS=https://newtz-production.up.railway.app
OWNER_EMAIL=your@gmail.com
METRICS_API_KEY=strong-random-secret

# Почта на Railway (SMTP :587 часто блокируют) — бесплатный вариант:
EMAIL_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
EMAIL_WEBHOOK_SECRET=your-secret

# AI (достаточно одного бесплатного ключа)
GEMINI_API_KEY=...
GROQ_API_KEY=...
AI_PROVIDER=auto
```

**Настройка Gmail webhook (бесплатно):** см. `scripts/gmail_email_webhook.gs` — Google Apps Script принимает POST от API и шлёт письма через твой Gmail.

---

## 2. Стек технологий

### Backend

| Компонент | Технология |
|---|---|
| Язык | Python 3.11 |
| Фреймворк | FastAPI 0.115 |
| ASGI-сервер | Uvicorn |
| Валидация | Pydantic 2 + pydantic-settings |
| HTTP-клиент | httpx (AI-провайдеры, email API) |
| Email | Jinja2-шаблоны + aiosmtplib / HTTP webhook / Mailjet / Brevo / Resend |
| Конфигурация | `.env` через python-dotenv |

### AI

| Провайдер | Модель по умолчанию | Назначение |
|---|---|---|
| Groq | `llama-3.1-8b-instant` | Бесплатный, быстрый |
| Google Gemini | `gemini-2.0-flash` | Бесплатный |
| OpenAI | `gpt-4o-mini` | Платный fallback |
| Локальный fallback | — | Keyword-классификатор без API |

Режим `AI_PROVIDER=auto`: цепочка Groq → Gemini → OpenAI (только настроенные ключи) → локальный fallback.

### Frontend

Статичная страница (HTML / CSS / JS), без фреймворков. Раздаётся тем же FastAPI-приложением.

### Инфраструктура

Docker, Railway, pytest, Postman-коллекция.

---

## 3. Архитектура

### Структура проекта

```
dev-landing-api/
├── app/
│   ├── main.py                    # FastAPI app, CORS, middleware, static
│   ├── config.py                  # Settings из .env
│   ├── api/routes/                # Controllers (тонкие роуты)
│   │   ├── contact.py             # POST /api/contact
│   │   ├── health.py              # GET /api/health
│   │   └── metrics.py             # GET /api/metrics
│   ├── schemas/contact.py         # Pydantic-модели запросов/ответов
│   ├── services/                  # Бизнес-логика
│   │   ├── contact_service.py     # Оркестрация: rate limit → AI → email → metrics
│   │   ├── ai_service.py          # AI-анализ + fallback
│   │   └── email_service.py       # Отправка писем
│   ├── repositories/              # Работа с файловым хранилищем
│   │   ├── rate_limit_repository.py
│   │   ├── metrics_repository.py
│   │   └── log_repository.py
│   ├── middleware/
│   │   ├── request_logger.py      # Логирование запросов
│   │   └── security.py            # Лимит body, security headers
│   └── core/
│       ├── exceptions.py          # AppError, RateLimitError, EmailDeliveryError
│       ├── error_handlers.py      # Глобальные обработчики
│       └── security.py            # IP, sanitize, honeypot
├── frontend/                      # Лендинг
├── templates/email/               # HTML-шаблоны писем
├── scripts/gmail_email_webhook.gs   # Apps Script для Railway
├── tests/test_api.py
├── postman/dev-landing-api.postman_collection.json
├── data/                          # Runtime: logs, metrics, rate_limit
├── Dockerfile
└── railway.toml
```

### Паттерны

- **Layered architecture:** Routes → Services → Repositories
- **Dependency injection через Settings:** конфиг читается один раз, передаётся в сервисы
- **Graceful degradation:** AI и email могут упасть — заявка всё равно принимается (soft-fail)
- **Repository pattern:** абстракция над JSON-файлами (логи, метрики, rate limit)

### Почему такие технологии

| Решение | Обоснование |
|---|---|
| **FastAPI** | Async, автогенерация OpenAPI, Pydantic-валидация из коробки |
| **Файлы вместо БД** | Для тестового объёма достаточно; проще деплой, нет миграций |
| **Несколько AI-провайдеров** | Бесплатные ключи (Groq/Gemini) + надёжный fallback |
| **Gmail Apps Script на Railway** | SMTP блокируется хостингом; HTTP webhook через свой Gmail — бесплатно и без домена |
| **Статичный frontend** | Минимум зависимостей, сразу видно интеграцию с API |

### Полный цикл обработки заявки

```
POST /api/contact
    → Rate limit (файл по IP)
    → Валидация (Pydantic)
    → AI-анализ комментария (Groq/Gemini/OpenAI → fallback)
    → Email владельцу + копия пользователю
    → Запись метрик
    → 201 Created + AI-результат в ответе
```

---

## 4. Реализация API

### Эндпоинты

| Method | Path | Описание | Auth |
|---|---|---|---|
| `GET` | `/` | Лендинг с формой | — |
| `POST` | `/api/contact` | Отправка формы | — |
| `GET` | `/api/health` | Статус сервиса | — |
| `GET` | `/api/metrics` | Статистика обращений | `X-Metrics-Key` |
| `GET` | `/docs` | Swagger UI | — |

### POST /api/contact

**Request body:**

```json
{
  "name": "Иван Петров",
  "phone": "+7 999 123-45-67",
  "email": "ivan@example.com",
  "comment": "Интересует сотрудничество по backend-проекту на FastAPI"
}
```

**Успех — 201 Created:**

```json
{
  "success": true,
  "message": "Обращение принято. Копия отправлена на ваш email.",
  "data": {
    "id": "cnt_a1b2c3d4e5f6",
    "created_at": "2026-07-29T20:00:00+00:00",
    "ai": {
      "sentiment": "positive",
      "sentiment_score": 0.85,
      "request_type": "collaboration",
      "summary": "Предложение о сотрудничестве по backend",
      "suggested_reply": "Здравствуйте, Иван! Спасибо за интерес...",
      "source": "gemini"
    }
  }
}
```

**Ошибка валидации — 422:**

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Комментарий: Комментарий должен быть не короче 10 символов",
    "details": [
      { "field": "comment", "message": "...", "label": "Комментарий" }
    ]
  }
}
```

**Rate limit — 429** (заголовки `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`):

```json
{
  "success": false,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Слишком много запросов. Попробуйте позже."
  }
}
```

### GET /api/health

```json
{
  "status": "ok",
  "timestamp": "2026-07-29T20:00:00+00:00",
  "version": "1.0.0",
  "checks": {
    "smtp_configured": true,
    "email_webhook_configured": true,
    "brevo_configured": false,
    "resend_configured": false,
    "email_configured": true,
    "gemini_configured": true,
    "ai_providers_available": ["gemini"],
    "data_dir_writable": true
  }
}
```

### GET /api/metrics

```bash
curl -H "X-Metrics-Key: your-secret" https://newtz-production.up.railway.app/api/metrics
```

```json
{
  "total_contacts": 12,
  "today": 3,
  "by_request_type": { "collaboration": 5, "question": 4, "other": 3 },
  "by_sentiment": { "positive": 8, "neutral": 3, "negative": 1 },
  "ai_fallback_count": 2,
  "rate_limited_count": 1
}
```

### Примеры curl

```bash
# Health
curl https://newtz-production.up.railway.app/api/health

# Contact
curl -X POST https://newtz-production.up.railway.app/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Петров",
    "phone": "+7 999 123-45-67",
    "email": "ivan@example.com",
    "comment": "Интересует сотрудничество по backend-проекту"
  }'

# Metrics
curl -H "X-Metrics-Key: your-secret" \
  https://newtz-production.up.railway.app/api/metrics
```

Postman-коллекция: `postman/dev-landing-api.postman_collection.json`.

### Валидация

| Поле | Правила |
|---|---|
| `name` | 2–100 символов, HTML-теги удаляются |
| `phone` | 10–15 цифр, regex формата |
| `email` | EmailStr (Pydantic) |
| `comment` | 10–2000 символов, санитизация |
| `company_fax` | Honeypot — если заполнено → spam |

### HTTP-статусы

| Код | Когда |
|---|---|
| `201` | Заявка принята |
| `401` | Неверный `X-Metrics-Key` |
| `403` | Metrics отключён (нет ключа в production) |
| `413` | Тело запроса > 32 KB |
| `422` | Ошибка валидации |
| `429` | Rate limit |
| `500` | Необработанная ошибка |

### Обработка ошибок

Единый формат ответа:

```json
{ "success": false, "error": { "code": "...", "message": "..." } }
```

Глобальные handlers в `app/core/error_handlers.py`:
- `AppError` — бизнес-ошибки (rate limit, email)
- `RequestValidationError` — 422 с деталями по полям
- `HTTPException` — стандартные HTTP-ошибки
- `Exception` — 500 + запись в `data/logs/errors-*.jsonl`

### Безопасность

- Санитизация HTML и control-символов в текстовых полях
- CRLF-инъекции в email subject/headers
- Honeypot `company_fax` против ботов
- Rate limiting по IP (SHA256-хеш в имени файла)
- `X-Forwarded-For` учитывается только при `TRUST_PROXY=true`
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- Metrics защищены ключом в production
- CORS через `ALLOWED_ORIGINS`

---

## 5. AI-интеграция

### Что делает AI

При каждой заявке AI анализирует комментарий и возвращает:

| Поле | Описание |
|---|---|
| `sentiment` | `positive` / `neutral` / `negative` |
| `sentiment_score` | 0.0–1.0 |
| `request_type` | `job_offer`, `collaboration`, `question`, `feedback`, `spam_suspicion`, `other` |
| `summary` | Краткое резюме на русском |
| `suggested_reply` | Черновик ответа пользователю (идёт в confirmation email) |

### Промпт

```
Разбери сообщение с формы контактов. Ответ — только JSON, без markdown и пояснений.

Нужные ключи:
sentiment (positive|neutral|negative),
sentiment_score (0..1),
request_type (job_offer|collaboration|question|feedback|spam_suspicion|other),
summary (по-русски, коротко),
suggested_reply (2–3 предложения, нормальный тон, без канцелярита).

Текст:
"""
{comment}
"""
```

### Fallback

1. **Цепочка провайдеров:** при `AI_PROVIDER=auto` — Groq → Gemini → OpenAI (только с ключами)
2. **При ошибке провайдера** — переход к следующему
3. **Локальный keyword-fallback** — словари русских ключевых слов для sentiment и request_type
4. В ответе поле `source`: `groq` / `gemini` / `openai` / `fallback`
5. Форма **всегда принимается**, даже если все AI-провайдеры недоступны

---

## 6. Что сделано с помощью AI (Cursor)

| Часть | AI / вручную |
|---|---|
| Каркас проекта, роуты, схемы Pydantic | Cursor (черновики) |
| AI-сервис, email-сервис, шаблоны | Cursor + ручная доработка |
| Rate limiting, security (XFF spoofing) | Вручную после тестирования |
| Gmail webhook для Railway | Вручную (обход блокировки SMTP) |
| Fallback AI, обработка ошибок Brevo/Mailjet | Вручную |
| Тесты, Postman, README | Вручную |

**Типичные промпты в Cursor:**
- «Сделай FastAPI contact form с валидацией и rate limit»
- «Добавь AI-анализ комментария через Gemini с fallback»
- «Исправь rate limit bypass через X-Forwarded-For»

**Что пришлось править руками:**
- SMTP на Railway не работает → Gmail Apps Script webhook
- Brevo требует активацию SMTP у саппорта → несколько email-провайдеров с приоритетом
- Soft-fail email: заявка принимается даже если письмо не ушло
- Honeypot вместо `website` (браузеры автозаполняют)

---

## 7. Хранение данных

База данных не используется. Всё в файловой системе под `DATA_DIR` (по умолчанию `./data`).

| Путь | Назначение |
|---|---|
| `data/logs/requests-YYYY-MM-DD.jsonl` | Лог каждого HTTP-запроса (method, path, status, duration, IP, request_id) |
| `data/logs/errors-YYYY-MM-DD.jsonl` | Необработанные исключения (traceback) |
| `data/rate_limit/<sha256-ip>.json` | Timestamps запросов по IP для rate limiting |
| `data/metrics.json` | Статистика: total, by type/sentiment, fallback count, rate_limited count, by day |

**Rate limiting:** sliding window — массив timestamps в JSON-файле на IP. По умолчанию 5 запросов / 3600 сек. Старые файлы (>24ч) удаляются автоматически.

**Метрики:** обновляются после каждой успешной заявки. Сами заявки (PII) не сохраняются — только агрегаты.

---

## Frontend

Статичный лендинг в `frontend/`:

- `index.html` — hero-секция + форма (name, phone, email, comment)
- `app.js` — `fetch POST /api/contact`, отображение статуса, переключение темы
- `styles.css` — адаптивная вёрстка, dark/light mode

Форма отправляет JSON на API, показывает сообщение об успехе или ошибку валидации. Honeypot-поле скрыто от пользователя.

---

## Лицензия

MIT (или по усмотрению автора).
