import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.core.security import get_client_ip, sanitize_header_value
from app.main import create_app


def _smtp_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM", "test@gmail.com")
    monkeypatch.setenv("OWNER_EMAIL", "owner@gmail.com")
    monkeypatch.setenv("BREVO_API_KEY", "")
    monkeypatch.setenv("MAILJET_API_KEY", "")
    monkeypatch.setenv("MAILJET_API_SECRET", "")
    monkeypatch.setenv("EMAIL_WEBHOOK_URL", "")
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("TRUST_PROXY", "false")
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()


@pytest.fixture
def app(tmp_path, monkeypatch):
    _smtp_env(monkeypatch, tmp_path)
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("ok", "degraded")
    assert body["checks"]["smtp_configured"] is True
    assert "ai_providers_available" in body["checks"]


@pytest.mark.asyncio
async def test_contact_validation_error(client):
    res = await client.post(
        "/api/contact",
        json={"name": "A", "phone": "123", "email": "bad", "comment": "short"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_contact_accepted_when_email_fails(client):
    from app.core.exceptions import EmailDeliveryError

    payload = {
        "name": "Иван Тестов",
        "phone": "+7 999 123-45-67",
        "email": "ivan@example.com",
        "comment": "Интересует сотрудничество по backend-проекту на FastAPI",
    }

    with patch(
        "app.services.email_service.EmailService.send_contact_emails",
        new_callable=AsyncMock,
        side_effect=EmailDeliveryError("SMTP down"),
    ):
        res = await client.post("/api/contact", json=payload)

    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert "принят" in body["message"].lower()


@pytest.mark.asyncio
async def test_contact_success_with_email_mock(client):
    payload = {
        "name": "Иван Тестов",
        "phone": "+7 999 123-45-67",
        "email": "ivan@example.com",
        "comment": "Интересует сотрудничество по backend-проекту на FastAPI",
    }

    with patch("app.services.email_service.EmailService.send_contact_emails", new_callable=AsyncMock):
        res = await client.post("/api/contact", json=payload)

    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["ai"]["source"] == "fallback"
    assert body["data"]["ai"]["request_type"] == "collaboration"


@pytest.mark.asyncio
async def test_rate_limit(tmp_path, monkeypatch):
    _smtp_env(monkeypatch, tmp_path)
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "2")
    get_settings.cache_clear()

    payload = {
        "name": "Иван Тестов",
        "phone": "+7 999 123-45-67",
        "email": "ivan@example.com",
        "comment": "Тестовое сообщение для rate limit проверки",
    }

    with patch("app.services.email_service.EmailService.send_contact_emails", new_callable=AsyncMock):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            assert (await ac.post("/api/contact", json=payload)).status_code == 201
            assert (await ac.post("/api/contact", json=payload)).status_code == 201
            assert (await ac.post("/api/contact", json=payload)).status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_xff_spoofing_ignored_without_trust_proxy(client):
    payload = {
        "name": "Иван Тестов",
        "phone": "+7 999 123-45-67",
        "email": "ivan@example.com",
        "comment": "Проверка обхода rate limit через поддельный X-Forwarded-For",
    }

    with patch("app.services.email_service.EmailService.send_contact_emails", new_callable=AsyncMock):
        for i in range(6):
            res = await client.post(
                "/api/contact",
                json=payload,
                headers={"X-Forwarded-For": f"1.2.3.{i}"},
            )
        assert res.status_code == 429


@pytest.mark.asyncio
async def test_metrics_blocked_in_production_without_key(tmp_path, monkeypatch):
    _smtp_env(monkeypatch, tmp_path)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("METRICS_API_KEY", "")
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/metrics")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_metrics_requires_valid_key(tmp_path, monkeypatch):
    _smtp_env(monkeypatch, tmp_path)
    monkeypatch.setenv("METRICS_API_KEY", "secret-key")
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get("/api/metrics")).status_code == 401
        res = await ac.get("/api/metrics", headers={"X-Metrics-Key": "secret-key"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_groq_ai_provider(tmp_path, monkeypatch):
    _smtp_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("AI_PROVIDER", "groq")
    get_settings.cache_clear()

    payload = {
        "name": "Иван",
        "phone": "+7 999 123-45-67",
        "email": "ivan@example.com",
        "comment": "Интересует сотрудничество по backend-проекту",
    }
    ai_json = {
        "sentiment": "positive",
        "sentiment_score": 0.9,
        "request_type": "collaboration",
        "summary": "Сотрудничество",
        "suggested_reply": "Спасибо!",
    }

    with patch("app.services.email_service.EmailService.send_contact_emails", new_callable=AsyncMock):
        with patch("app.services.ai_service.AIService._call_groq", new_callable=AsyncMock, return_value=ai_json):
            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/contact", json=payload)

    assert res.status_code == 201
    assert res.json()["data"]["ai"]["source"] == "groq"


def test_sanitize_header_value_strips_crlf():
    assert "\n" not in sanitize_header_value("test\r\nBcc: evil@x.com")


def test_get_client_ip_ignores_xff_when_not_trusted():
    class Req:
        headers = {"X-Forwarded-For": "8.8.8.8"}
        client = type("C", (), {"host": "127.0.0.1"})()

    assert get_client_ip(Req(), trust_proxy=False) == "127.0.0.1"
    assert get_client_ip(Req(), trust_proxy=True) == "8.8.8.8"
