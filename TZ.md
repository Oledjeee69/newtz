# ТЗ: Backend-сервис лендинга разработчика

**Срок сдачи:** 30 июля 2026, до 12:00 МСК  
**Формат сдачи:** GitHub + README + Postman/curl + деплой (или инструкция)  
**Статус:** черновик ТЗ для реализации

---

## 1. Цель проекта

Разработать backend-сервис для лендинга-презентации разработчика с REST API, обработкой формы обратной связи, email-уведомлениями, AI-обработкой обращений и наблюдаемостью (логи, метрики, health).

**Критерий «сдано»:** полный цикл  
`запрос → валидация → бизнес-логика → AI → email → ответ`

---

## 2. Выбор стека (рекомендация)

| Компонент | Решение | Почему |
|-----------|---------|--------|
| Язык | **Python 3.11+** | Быстрая разработка, сильная экосистема для API и AI |
| Фреймворк | **FastAPI** | Встроенный OpenAPI/Swagger, Pydantic-валидация, async |
| Валидация | **Pydantic v2** | Декларативные схемы, понятные ошибки 422 |
| AI | **OpenAI API** (`gpt-4o-mini`) | Дёшево, стабильно, хорошо для классификации и тональности |
| Email | **aiosmtplib** + Jinja2-шаблоны | Async SMTP без тяжёлых зависимостей |
| Хранение | **Файловая система (JSON)** | Соответствует ТЗ, без обязательной БД |
| Rate limit | **JSON-кеш по IP** | Простой sliding window, без Redis |
| Логи | **structlog** → файл + stdout | Структурированные JSON-логи |
| Деплой | **Railway / Render** | Бесплатный tier, env vars, HTTPS из коробки |
| Фронт (бонус) | **HTML + vanilla JS** или Next.js static | Показать интеграцию с API |

**Альтернатива (если нужен PHP):** Laravel 11 + OpenAI PHP client + Monolog + файловый cache для rate limit.  
Для тестового с акцентом на API и Swagger — **FastAPI предпочтительнее**.

---

## 3. Архитектура

### 3.1. Слои

```
Controllers (routes)  →  Services  →  Repositories / Handlers
         ↓                    ↓
    Middleware          External (AI, SMTP)
```

| Слой | Ответственность |
|------|-----------------|
| **Routes** | HTTP, статус-коды, вызов сервисов |
| **Schemas** | Request/Response DTO (Pydantic) |
| **Services** | Бизнес-логика: contact flow, AI, email |
| **Repositories** | Чтение/запись JSON (логи, метрики, rate limit) |
| **Handlers** | Глобальные исключения, CORS, request logging |
| **Core** | Config, exceptions, constants |

### 3.2. Структура проекта

```
dev-landing-api/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, middleware
│   ├── config.py               # Settings из .env (pydantic-settings)
│   ├── api/
│   │   └── routes/
│   │       ├── contact.py      # POST /api/contact
│   │       ├── health.py       # GET /api/health
│   │       └── metrics.py      # GET /api/metrics
│   ├── schemas/
│   │   ├── contact.py          # ContactRequest, ContactResponse
│   │   ├── health.py
│   │   └── metrics.py
│   ├── services/
│   │   ├── contact_service.py  # Оркестратор полного цикла
│   │   ├── ai_service.py       # AI: тональность + классификация
│   │   └── email_service.py    # SMTP: owner + user copy
│   ├── repositories/
│   │   ├── log_repository.py
│   │   ├── metrics_repository.py
│   │   └── rate_limit_repository.py
│   ├── middleware/
│   │   └── request_logger.py
│   └── core/
│       ├── exceptions.py       # AppError, ValidationError, RateLimitError
│       └── error_handlers.py
├── data/                       # gitignore, создаётся при старте
│   ├── logs/
│   │   └── requests-YYYY-MM-DD.jsonl
│   ├── metrics.json
│   └── rate_limit/
│       └── {ip_hash}.json
├── templates/email/
│   ├── owner_notification.html
│   └── user_confirmation.html
├── tests/
│   ├── test_contact.py
│   ├── test_rate_limit.py
│   └── test_ai_fallback.py
├── postman/
│   └── dev-landing-api.postman_collection.json
├── .env.example
├── requirements.txt
├── Dockerfile
├── README.md
└── TZ.md
```

### 3.3. Паттерны

- **Service Layer** — вся бизнес-логика вне роутов
- **Repository** — абстракция над файловым хранилищем
- **DTO (Schemas)** — отделение API-контракта от внутренних моделей
- **Graceful Degradation** — AI-ошибка не ломает отправку формы
- **Fail-safe logging** — ошибка записи лога не отменяет ответ клиенту

---

## 4. API-спецификация

### 4.1. POST `/api/contact` (обязательный)

**Назначение:** приём обращения с лендинга.

**Request body (JSON):**

```json
{
  "name": "Иван Петров",
  "phone": "+7 (999) 123-45-67",
  "email": "ivan@example.com",
  "comment": "Интересует сотрудничество по backend-проекту"
}
```

**Валидация:**

| Поле | Правила |
|------|---------|
| `name` | 2–100 символов, trim, без HTML |
| `phone` | 10–20 символов, regex `^[\d\s\-\+\(\)]+$` |
| `email` | EmailStr (Pydantic) |
| `comment` | 10–2000 символов, trim, базовая санитизация |

**Успешный ответ `201 Created`:**

```json
{
  "success": true,
  "message": "Обращение принято. Копия отправлена на ваш email.",
  "data": {
    "id": "cnt_01H...",
    "created_at": "2026-07-30T08:30:00Z",
    "ai": {
      "sentiment": "positive",
      "sentiment_score": 0.82,
      "request_type": "collaboration",
      "summary": "Запрос на backend-сотрудничество"
    }
  }
}
```

**Ошибки:**

| Код | Когда |
|-----|-------|
| `400` | Невалидный JSON |
| `422` | Ошибки валидации полей |
| `429` | Rate limit превышен |
| `500` | Неожиданная ошибка (без утечки stack trace) |
| `503` | SMTP недоступен (опционально, если email критичен) |

**Порядок обработки (ContactService):**

1. Проверить rate limit по IP (`X-Forwarded-For` / `client.host`)
2. Валидировать и санитизировать данные
3. Вызвать `AIService.analyze(comment)` с timeout 5 с
4. При ошибке AI → `ai_result = null`, записать warning в лог, **продолжить**
5. Отправить email владельцу (с AI-метаданными, если есть)
6. Отправить копию пользователю (с AI-сгенерированным текстом благодарности или шаблоном по умолчанию)
7. Записать метрики (+1 обращение, тип, тональность)
8. Залогировать запрос
9. Вернуть `201`

---

### 4.2. GET `/api/health` (рекомендуется)

**Ответ `200`:**

```json
{
  "status": "ok",
  "timestamp": "2026-07-30T08:30:00Z",
  "version": "1.0.0",
  "checks": {
    "smtp_configured": true,
    "openai_configured": true,
    "data_dir_writable": true
  }
}
```

`status: "degraded"` — если AI или SMTP не настроены, но сервис жив.

---

### 4.3. GET `/api/metrics` (рекомендуется)

**Query:** `?period=7d` (опционально)

**Ответ `200`:**

```json
{
  "total_contacts": 42,
  "today": 3,
  "by_request_type": {
    "collaboration": 15,
    "job_offer": 10,
    "question": 12,
    "other": 5
  },
  "by_sentiment": {
    "positive": 28,
    "neutral": 10,
    "negative": 4
  },
  "ai_fallback_count": 2,
  "rate_limited_count": 7
}
```

**Защита (опционально):** заголовок `X-Metrics-Key` или basic auth через env.

---

## 5. AI-интеграция

### 5.1. Функции (минимум 2 в одном вызове)

Один запрос к OpenAI возвращает JSON:

```json
{
  "sentiment": "positive | neutral | negative",
  "sentiment_score": 0.0-1.0,
  "request_type": "job_offer | collaboration | question | feedback | spam_suspicion | other",
  "summary": "краткое описание в 1 предложении",
  "suggested_reply": "персонализированный текст для письма пользователю"
}
```

### 5.2. Промпт (черновик)

```
Ты — ассистент backend-сервиса лендинга разработчика.
Проанализируй комментарий пользователя и верни ТОЛЬКО валидный JSON без markdown.

Поля:
- sentiment: positive | neutral | negative
- sentiment_score: число от 0 до 1
- request_type: job_offer | collaboration | question | feedback | spam_suspicion | other
- summary: краткое описание на русском (до 120 символов)
- suggested_reply: вежливый ответ пользователю на русском (2-3 предложения)

Комментарий:
"""
{comment}
"""
```

**Модель:** `gpt-4o-mini` (дёшево, быстро).  
**Параметры:** `temperature=0.2`, `response_format={"type": "json_object"}`.

### 5.3. Fallback

| Сценарий | Поведение |
|----------|-----------|
| OpenAI timeout / 5xx | `ai: null`, emails по дефолтным шаблонам |
| Невалидный JSON от модели | retry 1 раз → fallback |
| `OPENAI_API_KEY` пуст | сервис стартует, AI отключён (`health.checks.openai_configured: false`) |
| Ключ есть, но quota exceeded | fallback + increment `ai_fallback_count` |

Пользователь **всегда** получает `201`, если валидация и SMTP прошли.

---

## 6. Email

### 6.1. Письмо владельцу

- **To:** `OWNER_EMAIL` из env
- **Subject:** `[Лендинг] Новое обращение: {request_type или "новое"}`
- **Body:** имя, телефон, email, комментарий, AI summary, sentiment, тип

### 6.2. Копия пользователю

- **To:** email из формы
- **Subject:** `Спасибо за обращение!`
- **Body:** `suggested_reply` от AI или статический шаблон

### 6.3. SMTP (env)

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=noreply@yourdomain.com
OWNER_EMAIL=you@example.com
```

**Dev:** [Mailtrap](https://mailtrap.io) или Ethereal Email.

---

## 7. Rate limiting

**Алгоритм:** fixed window или sliding window в JSON-файле.

```env
RATE_LIMIT_MAX_REQUESTS=5
RATE_LIMIT_WINDOW_SECONDS=3600
```

**Ключ:** SHA256(IP + optional salt).  
**При превышении:** `429` + заголовки:

```
Retry-After: 1800
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
```

**Очистка:** удалять файлы старше 24 ч при каждом запросе (lazy cleanup).

---

## 8. Логирование

### 8.1. Request log (обязательно)

Каждый HTTP-запрос → `data/logs/requests-YYYY-MM-DD.jsonl`:

```json
{
  "timestamp": "2026-07-30T08:30:00.123Z",
  "method": "POST",
  "path": "/api/contact",
  "status_code": 201,
  "duration_ms": 842,
  "client_ip": "1.2.3.4",
  "user_agent": "...",
  "request_id": "req_...",
  "error": null
}
```

**Не логировать:** полный текст комментария в production (или маскировать email/phone).

### 8.2. Error log

Отдельный `data/logs/errors-YYYY-MM-DD.jsonl` для исключений с traceback (только server-side).

---

## 9. Безопасность

- [ ] Валидация и санитизация всех полей
- [ ] Rate limiting по IP
- [ ] CORS: whitelist `ALLOWED_ORIGINS` (не `*` в production)
- [ ] Не отдавать внутренние ошибки клиенту
- [ ] `.env` в `.gitignore`
- [ ] Honeypot-поле `website` на фронте (скрытое) — бонус против ботов
- [ ] Ограничение размера body (FastAPI default + явный limit)

---

## 10. Переменные окружения (.env.example)

```env
# App
APP_NAME=Dev Landing API
APP_VERSION=1.0.0
DEBUG=false
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:5500

# Data
DATA_DIR=./data

# Rate limit
RATE_LIMIT_MAX_REQUESTS=5
RATE_LIMIT_WINDOW_SECONDS=3600

# SMTP
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
OWNER_EMAIL=

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=5

# Metrics (optional)
METRICS_API_KEY=
```

---

## 11. Фронтенд (бонус, + к оценке)

Минимальный лендинг на 1 страницу:

- Hero: имя, стек, CTA
- Секция «Обо мне»
- Форма: name, phone, email, comment
- Отправка на `POST /api/contact`
- Состояния: loading / success / error (в т.ч. 429)
- Адаптив, тёмная тема

Можно вынести в `frontend/` в том же репо или отдельный static на GitHub Pages.

---

## 12. Деплой

### Вариант A: Railway (рекомендуется)

1. Push в GitHub
2. New Project → Deploy from GitHub
3. Env vars из `.env.example`
4. `DATA_DIR=/app/data` + persistent volume (если нужны метрики между рестартами)
5. Health check: `GET /api/health`

### Вариант B: Локально + ngrok

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
ngrok http 8000
```

В README указать публичный URL ngrok.

---

## 13. README (чеклист для сдачи)

1. **Запуск** — install, env, `uvicorn`, docker
2. **Стек** — Python, FastAPI, OpenAI, SMTP, structlog
3. **Архитектура** — схема слоёв + почему FastAPI
4. **API** — таблица эндпоинтов, примеры curl
5. **AI** — промпт, fallback, что делает каждое поле
6. **Что сделано с AI** — честный раздел (генерация boilerplate, тесты, правки вручную)
7. **Хранение** — пути к логам, rate limit, metrics.json
8. **Деплой** — ссылка или ngrok-инструкция
9. **Postman** — коллекция в репо

---

## 14. План работ (до 30.07 12:00 МСК)

| Этап | Время | Результат |
|------|-------|-----------|
| 1. Каркас FastAPI + config + error handlers | 1–2 ч | `GET /health`, Swagger |
| 2. Repositories (logs, metrics, rate limit) | 1–2 ч | Файловое хранилище |
| 3. POST /contact без AI и email | 1 ч | Валидация + 201 |
| 4. Email service + шаблоны | 1–2 ч | 2 письма |
| 5. AI service + fallback | 1–2 ч | Анализ комментария |
| 6. ContactService (полный цикл) | 1 ч | Интеграция |
| 7. GET /metrics + middleware logging | 1 ч | Метрики и логи |
| 8. Тесты (pytest) | 1–2 ч | contact, rate limit, fallback |
| 9. README + Postman + деплой | 1–2 ч | Сдача |
| 10. Фронт (бонус) | 2–3 ч | Лендинг + форма |

**Итого:** ~12–16 часов чистой работы. Уложиться реально за 1–2 вечера.

---

## 15. Критерии приёмки (self-check перед push)

- [ ] `POST /api/contact` работает end-to-end
- [ ] Валидация отдаёт `422` с понятными полями
- [ ] Rate limit отдаёт `429`
- [ ] AI вызывается и результат в ответе + в письме владельцу
- [ ] При отключённом OpenAI форма всё равно работает
- [ ] 2 email уходят (owner + user)
- [ ] Логи пишутся в файл на каждый запрос
- [ ] Swagger доступен на `/docs`
- [ ] CORS настроен
- [ ] README полный
- [ ] Postman/curl примеры
- [ ] Публичный URL или инструкция

---

## 16. Что написать в README про использование AI (шаблон)

> **С помощью AI (Cursor / ChatGPT):**  
> - черновик структуры проекта и Pydantic-схем  
> - boilerplate FastAPI routes и error handlers  
> - черновик промпта для анализа комментария  
> - примеры unit-тестов  
>
> **Вручную:**  
> - бизнес-логика ContactService и порядок fallback  
> - rate limiting и формат логов  
> - SMTP-шаблоны и обработка edge cases  
> - финальная валидация regex телефона  
> - деплой и env-конфигурация

---

## 17. Открытые решения (утвердить перед кодом)

| # | Вопрос | Рекомендация |
|---|--------|--------------|
| 1 | Делать фронт? | Да, простой static — сильный плюс |
| 2 | Какой AI-провайдер? | OpenAI (есть бесплатные кредиты) |
| 3 | Деплой? | Railway + ngrok как запасной |
| 4 | Защита /metrics? | API key в env |
| 5 | БД? | Не нужна для MVP; JSON достаточно |

---

*Документ готов к реализации. Следующий шаг: scaffold FastAPI-проекта по структуре из §3.2.*
