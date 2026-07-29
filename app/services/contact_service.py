import logging
import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.core.exceptions import EmailDeliveryError
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.rate_limit_repository import RateLimitRepository
from app.schemas.contact import ContactData, ContactRequest, ContactResponse
from app.services.ai_service import AIService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


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

        email_ok = True
        email_error = ""
        try:
            await self._email.send_contact_emails(payload, ai_result)
        except EmailDeliveryError as exc:
            email_ok = False
            email_error = exc.message
            logger.warning("Email delivery failed, contact still accepted: %s", exc.message)

        contact_id = f"cnt_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        await self._metrics.record_contact(
            request_type=ai_result.request_type,
            sentiment=ai_result.sentiment,
            ai_fallback=ai_fallback,
        )

        message = (
            "Обращение принято. Копия отправлена на ваш email."
            if email_ok
            else f"Обращение принято. Письмо не отправилось: {email_error}"
        )

        return ContactResponse(
            message=message,
            data=ContactData(id=contact_id, created_at=created_at, ai=ai_result),
        )

    def rate_limit_remaining(self, client_ip: str) -> int:
        return self._rate_limit.remaining(client_ip)
