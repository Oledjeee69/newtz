import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import sanitize_text_field

PHONE_PATTERN = re.compile(r"^[\d\s\-\+\(\)\.]{7,25}$")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

FIELD_LABELS = {
    "name": "Имя",
    "phone": "Телефон",
    "email": "Email",
    "comment": "Комментарий",
}


def strip_html(value: str) -> str:
    return HTML_TAG_PATTERN.sub("", value).strip()


def count_digits(value: str) -> int:
    return sum(1 for ch in value if ch.isdigit())


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=25)
    email: EmailStr
    comment: str = Field(..., min_length=10, max_length=2000)
    company_fax: str | None = Field(default=None, description="Honeypot — must be empty")

    @field_validator("name", "comment")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        cleaned = strip_html(sanitize_text_field(v))
        if not cleaned:
            raise ValueError("Поле не может быть пустым")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("Некорректный формат телефона")
        digits = count_digits(cleaned)
        if digits < 10 or digits > 15:
            raise ValueError("Телефон должен содержать от 10 до 15 цифр")
        return cleaned

    @field_validator("company_fax")
    @classmethod
    def honeypot(cls, v: str | None) -> str | None:
        if v and v.strip():
            raise ValueError("Spam detected")
        return v


class AIAnalysis(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    sentiment_score: float = Field(ge=0.0, le=1.0)
    request_type: Literal[
        "job_offer", "collaboration", "question", "feedback", "spam_suspicion", "other"
    ]
    summary: str
    suggested_reply: str
    source: Literal["openai", "groq", "gemini", "fallback"] = "fallback"


class ContactData(BaseModel):
    id: str
    created_at: str
    ai: AIAnalysis | None = None


class ContactResponse(BaseModel):
    success: bool = True
    message: str
    data: ContactData


class HealthChecks(BaseModel):
    smtp_configured: bool
    brevo_configured: bool
    resend_configured: bool
    email_configured: bool
    openai_configured: bool
    groq_configured: bool
    gemini_configured: bool
    ai_providers_available: list[str]
    data_dir_writable: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    timestamp: str
    version: str
    checks: HealthChecks


class MetricsResponse(BaseModel):
    total_contacts: int
    today: int
    by_request_type: dict[str, int]
    by_sentiment: dict[str, int]
    ai_fallback_count: int
    rate_limited_count: int
