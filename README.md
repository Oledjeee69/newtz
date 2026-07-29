# contact-api

Небольшой backend под мою форму «написать мне»: валидация, письмо на почту, простая аналитика текста через AI, лимит по IP, логи в файлы. Рядом лежит статичная страница, чтобы можно было сразу ткнуть и проверить.

Идея простая — показать, что я не только верстаю, а умею собрать API и довести его до рабочего состояния (в т.ч. на Railway).

## Запуск

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` нужны Gmail App Password и хотя бы один AI-ключ (Gemini или Groq — бесплатно). Без AI тоже работает: есть свой классификатор по словам.

```bash
uvicorn app.main:app --reload --port 8000
```

Открой http://localhost:8000 — форма. Документация API: `/docs`.

## Что внутри

- `POST /api/contact` — основная ручка
- `GET /api/health` — жив ли сервис и что настроено
- `GET /api/metrics` — счётчики (в проде нужен `X-Metrics-Key`)

Слои обычные: роуты тонкие, логика в сервисах, JSON на диске вместо БД (для такого объёма хватает). Если AI отвалился — форма всё равно уходит, в ответе `source: fallback`.

Письма: локально через Gmail SMTP; на Railway SMTP часто таймаутится — лучше `RESEND_API_KEY` (HTTP). Если почта упала, заявка всё равно принимается.

## Env (коротко)

Смотри `.env.example`. На Railway важно:

- `TRUST_PROXY=true`
- `ALLOWED_ORIGINS` = твой публичный URL
- `METRICS_API_KEY` = нормальный секрет
- `DEBUG=false`
- `RESEND_API_KEY` — иначе письма с Railway не уйдут (SMTP блокируют)
- `OWNER_EMAIL` — куда слать заявки

## Деплой

Dockerfile уже есть, `railway.toml` смотрит на `/api/health`.

```bash
railway up
# или
docker build -t contact-api . && docker run -p 8000:8000 --env-file .env contact-api
```

## Тесты / Postman

```bash
pytest -v
```

Коллекция: `postman/dev-landing-api.postman_collection.json`.

## Заметки по безопасности

По ходу ловил обход rate limit через `X-Forwarded-For` — теперь заголовок читаю только если `TRUST_PROXY=true`. В письмах чищу CRLF в subject/name. Metrics без ключа в проде не отдаю. На форме honeypot `company_fax` (поле `website` браузеры сами заполняют — бесит).

## Про AI в разработке

Cursor помогал с каркасом и черновиками. Rate limit, SMTP, fallback и правки под реальные баги — руками.
