# Security Review — Dev Landing API

Проведён self-pentest перед сдачей тестового задания.

## Найденные проблемы и исправления

| # | Уязвимость | Риск | Исправление |
|---|-----------|------|-------------|
| 1 | **Rate limit bypass** через поддельный `X-Forwarded-For` | High | IP берётся из заголовка только при `TRUST_PROXY=true` (Railway). Локально — `request.client.host` |
| 2 | **Email header injection** (CRLF в name/subject) | High | `sanitize_header_value()` — удаление `\r\n` и control chars |
| 3 | **Публичный `/api/metrics`** без ключа | Medium | В production (`DEBUG=false`) endpoint закрыт без `METRICS_API_KEY` |
| 4 | **Honeypot `website`** автозаполнялся браузером | Medium | Переименован в `company_fax`, не отправляется если пуст |
| 5 | **Нет лимита размера body** | Medium | `SecurityMiddleware` — max 32 KB (`MAX_REQUEST_BODY_BYTES`) |
| 6 | **Нет security headers** | Low | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` |
| 7 | **XSS в email-шаблонах** | Low | Jinja2 `autoescape` для HTML-шаблонов |
| 8 | **Control chars в полях формы** | Low | `sanitize_text_field()` в валидаторах Pydantic |

## Что проверяли

```bash
# Rate limit bypass (должен вернуть 429 на 6-й запрос с разными X-Forwarded-For)
for i in {1..6}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/api/contact \
    -H "Content-Type: application/json" \
    -H "X-Forwarded-For: 1.2.3.$i" \
    -d '{"name":"Test","phone":"89991234567","email":"t@t.com","comment":"Тестовый комментарий длинный"}'
done

# Header injection (должен пройти валидацию, CRLF убраны)
curl -X POST http://localhost:8001/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Test\r\nBcc: evil@x.com","phone":"89991234567","email":"t@t.com","comment":"Тест инъекции в заголовок"}'

# Metrics без ключа (403 в production)
curl http://localhost:8001/api/metrics

# Oversized payload (413)
python -c "print('{\"comment\":\"' + 'x'*40000 + '\"}')" | curl -X POST ... 
```

## Рекомендации для production (Railway)

```env
TRUST_PROXY=true
DEBUG=false
METRICS_API_KEY=<random-32-chars>
ALLOWED_ORIGINS=https://your-app.up.railway.app
```

## Остаточные риски

- **File-based rate limit** — не распределённый (для одного инстанса OK)
- **Нет CAPTCHA** — honeypot + rate limit достаточно для MVP
- **AI prompt injection** — комментарий передаётся в LLM; риск низкий, данные не выполняются как код

## Автотесты безопасности

`pytest tests/test_api.py` — включает тесты на rate limit bypass, metrics auth, header sanitization.
