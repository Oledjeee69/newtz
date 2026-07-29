from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.contact import HealthChecks, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    data_writable = False
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        test_file = settings.data_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        data_writable = True
    except OSError:
        data_writable = False

    providers = settings.ai_provider_chain or ["fallback"]

    checks = HealthChecks(
        smtp_configured=settings.smtp_configured,
        openai_configured=settings.openai_configured,
        groq_configured=settings.groq_configured,
        gemini_configured=settings.gemini_configured,
        ai_providers_available=providers,
        data_dir_writable=data_writable,
    )

    status = "ok" if data_writable else "degraded"
    if not settings.smtp_configured:
        status = "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
        checks=checks,
    )
