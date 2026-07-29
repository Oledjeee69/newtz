import logging
from email.utils import formataddr
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.core.exceptions import EmailDeliveryError
from app.core.security import sanitize_header_value
from app.schemas.contact import AIAnalysis, ContactRequest

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "email"


class EmailService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def send_contact_emails(self, contact: ContactRequest, ai: AIAnalysis | None) -> None:
        if not self._settings.smtp_configured:
            raise EmailDeliveryError("SMTP не настроен. Проверьте переменные окружения.")

        await self._send_owner(contact, ai)
        await self._send_user_copy(contact, ai)

    async def _send_owner(self, contact: ContactRequest, ai: AIAnalysis | None) -> None:
        template = self._env.get_template("owner_notification.html")
        request_type = ai.request_type if ai else "other"
        html = template.render(
            name=contact.name,
            phone=contact.phone,
            email=contact.email,
            comment=contact.comment,
            ai=ai,
            request_type=request_type,
        )
        subject = sanitize_header_value(f"[Лендинг] Новое обращение: {request_type}")
        await self._send(self._settings.owner_email, subject, html)

    async def _send_user_copy(self, contact: ContactRequest, ai: AIAnalysis | None) -> None:
        template = self._env.get_template("user_confirmation.html")
        reply_text = (
            ai.suggested_reply
            if ai
            else f"Здравствуйте, {contact.name}! Спасибо за обращение. Я свяжусь с вами в ближайшее время."
        )
        html = template.render(name=contact.name, reply_text=reply_text)
        await self._send(str(contact.email), "Спасибо за обращение!", html)

    async def _send(self, to: str, subject: str, html: str) -> None:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        safe_to = sanitize_header_value(to, 254)
        safe_subject = sanitize_header_value(subject, 200)
        safe_from = sanitize_header_value(self._settings.smtp_from, 254)

        message = MIMEMultipart("alternative")
        message["From"] = formataddr(("Олег", safe_from))
        message["To"] = safe_to
        message["Subject"] = safe_subject
        message.attach(MIMEText(html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                message,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=self._settings.smtp_user,
                password=self._settings.smtp_password,
                start_tls=True,
            )
        except Exception as exc:
            logger.exception("SMTP send failed to %s", to)
            raise EmailDeliveryError("Не удалось отправить email") from exc
