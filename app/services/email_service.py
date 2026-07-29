import logging
from email.utils import formataddr
from pathlib import Path

import aiosmtplib
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.core.exceptions import EmailDeliveryError
from app.core.security import sanitize_header_value
from app.schemas.contact import AIAnalysis, ContactRequest

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "email"
SMTP_TIMEOUT = 12


class EmailService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    @property
    def _smtp_password(self) -> str:
        return self._settings.smtp_password.replace(" ", "")

    async def send_contact_emails(self, contact: ContactRequest, ai: AIAnalysis | None) -> None:
        if not self._settings.email_configured:
            raise EmailDeliveryError(
                "Email не настроен (EMAIL_WEBHOOK_URL, MAILJET_*, BREVO, RESEND или SMTP)."
            )

        owner_html, owner_subject = self._owner_content(contact, ai)
        user_html, user_subject = self._user_content(contact, ai)

        # Отправляем независимо: одно письмо не должно блокировать второе
        errors: list[str] = []
        for to, subject, html in (
            (self._settings.owner_email, owner_subject, owner_html),
            (str(contact.email), user_subject, user_html),
        ):
            try:
                await self._deliver(to, subject, html)
            except EmailDeliveryError as exc:
                errors.append(f"{to}: {exc.message}")
                logger.warning("Email failed for %s: %s", to, exc.message)

        if len(errors) == 2:
            raise EmailDeliveryError("; ".join(errors))
        if errors:
            # Одно из двух ушло — заявку считаем доставленной частично
            logger.warning("Partial email delivery: %s", "; ".join(errors))

    def _owner_content(self, contact: ContactRequest, ai: AIAnalysis | None) -> tuple[str, str]:
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
        subject = sanitize_header_value(f"[Contact] Новое обращение: {request_type}")
        return html, subject

    def _user_content(self, contact: ContactRequest, ai: AIAnalysis | None) -> tuple[str, str]:
        template = self._env.get_template("user_confirmation.html")
        reply_text = (
            ai.suggested_reply
            if ai
            else f"Здравствуйте, {contact.name}! Спасибо за обращение. Я свяжусь с вами в ближайшее время."
        )
        html = template.render(name=contact.name, reply_text=reply_text)
        return html, "Спасибо за обращение!"

    async def _deliver(self, to: str, subject: str, html: str) -> None:
        # HTTP первыми: Railway режет SMTP. Webhook (Apps Script/Gmail) — бесплатно.
        if self._settings.email_webhook_configured:
            await self._send_webhook(to, subject, html)
            return
        if self._settings.mailjet_configured:
            await self._send_mailjet(to, subject, html)
            return
        if self._settings.brevo_configured:
            await self._send_brevo(to, subject, html)
            return
        if self._settings.resend_configured:
            await self._send_resend(to, subject, html)
            return
        await self._send_smtp(to, subject, html)

    async def _send_webhook(self, to: str, subject: str, html: str) -> None:
        payload = {
            "secret": self._settings.email_webhook_secret,
            "to": to,
            "subject": subject,
            "html": html,
            "fromName": "Contact API",
        }
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.post(
                    self._settings.email_webhook_url.strip(),
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if response.is_error:
                    detail = response.text[:300]
                    logger.error("Email webhook HTTP %s to %s: %s", response.status_code, to, detail)
                    raise EmailDeliveryError(f"Webhook {response.status_code}: {detail}")
                # Apps Script может вернуть 200 с ok:false
                try:
                    body = response.json()
                    if isinstance(body, dict) and body.get("ok") is False:
                        raise EmailDeliveryError(f"Webhook rejected: {body.get('error', 'ok=false')}")
                except EmailDeliveryError:
                    raise
                except Exception:
                    pass
        except EmailDeliveryError:
            raise
        except Exception as exc:
            logger.exception("Email webhook failed to %s", to)
            raise EmailDeliveryError(f"Не удалось отправить через EMAIL_WEBHOOK_URL: {exc}") from exc

    async def _send_mailjet(self, to: str, subject: str, html: str) -> None:
        payload = {
            "Messages": [
                {
                    "From": {
                        "Email": self._settings.mailjet_sender_email.strip(),
                        "Name": self._settings.mailjet_sender_name,
                    },
                    "To": [{"Email": to}],
                    "Subject": subject,
                    "HTMLPart": html,
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.mailjet.com/v3.1/send",
                    auth=(
                        self._settings.mailjet_api_key.strip(),
                        self._settings.mailjet_api_secret.strip(),
                    ),
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if response.is_error:
                    detail = response.text[:300]
                    logger.error("Mailjet HTTP %s to %s: %s", response.status_code, to, detail)
                    raise EmailDeliveryError(f"Mailjet {response.status_code}: {detail}")
        except EmailDeliveryError:
            raise
        except Exception as exc:
            logger.exception("Mailjet send failed to %s", to)
            raise EmailDeliveryError(f"Не удалось отправить email через Mailjet: {exc}") from exc

    async def _send_brevo(self, to: str, subject: str, html: str) -> None:
        payload = {
            "sender": {
                "name": self._settings.brevo_sender_name,
                "email": self._settings.brevo_sender_email.strip(),
            },
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "api-key": self._settings.brevo_api_key.strip(),
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
                if response.is_error:
                    detail = response.text[:300]
                    logger.error("Brevo HTTP %s to %s: %s", response.status_code, to, detail)
                    raise EmailDeliveryError(f"Brevo {response.status_code}: {detail}")
        except EmailDeliveryError:
            raise
        except Exception as exc:
            logger.exception("Brevo send failed to %s", to)
            raise EmailDeliveryError(f"Не удалось отправить email через Brevo: {exc}") from exc

    async def _send_resend(self, to: str, subject: str, html: str) -> None:
        payload = {
            "from": self._settings.resend_from,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self._settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except Exception as exc:
            logger.exception("Resend send failed to %s", to)
            raise EmailDeliveryError("Не удалось отправить email через Resend") from exc

    async def _send_smtp(self, to: str, subject: str, html: str) -> None:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        safe_to = sanitize_header_value(to, 254)
        safe_subject = sanitize_header_value(subject, 200)
        safe_from = sanitize_header_value(self._settings.smtp_from, 254)

        message = MIMEMultipart("alternative")
        message["From"] = formataddr(("Contact API", safe_from))
        message["To"] = safe_to
        message["Subject"] = safe_subject
        message.attach(MIMEText(html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                message,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=self._settings.smtp_user,
                password=self._smtp_password,
                start_tls=True,
                timeout=SMTP_TIMEOUT,
            )
        except Exception as exc:
            logger.exception("SMTP send failed to %s", to)
            raise EmailDeliveryError(
                "SMTP недоступен с хостинга (часто блокируют порт 587). Добавьте RESEND_API_KEY."
            ) from exc
