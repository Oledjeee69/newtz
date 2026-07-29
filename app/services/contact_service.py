import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.rate_limit_repository import RateLimitRepository
from app.schemas.contact import ContactData, ContactRequest, ContactResponse
from app.services.ai_service import AIService
from app.services.email_service import EmailService


class ContactService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._rate_limit = RateLimitRepository(settings)
        self._metrics = MetricsRepository(settings)
        self._ai = AIService(settings)
        self._email = EmailService(settings)

    async def submit(self, payload: ContactRequest, client_ip: str) -> ContactResponse:
        await self._rate_limit.check_and_increment(client_ip)

        ai_result = await self._ai.analyze(payload.comment, payload.name)
        ai_fallback = ai_result.source == "fallback"

        await self._email.send_contact_emails(payload, ai_result)

        contact_id = f"cnt_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        await self._metrics.record_contact(
            request_type=ai_result.request_type,
            sentiment=ai_result.sentiment,
            ai_fallback=ai_fallback,
        )

        return ContactResponse(
            message="Принял. Копию кинул тебе на почту.",
            data=ContactData(id=contact_id, created_at=created_at, ai=ai_result),
        )

    def rate_limit_remaining(self, client_ip: str) -> int:
        return self._rate_limit.remaining(client_ip)
