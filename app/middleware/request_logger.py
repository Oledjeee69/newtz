import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.core.security import get_client_ip
from app.repositories.log_repository import LogRepository
from app.repositories.metrics_repository import MetricsRepository


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        log_repo = LogRepository(settings)
        metrics_repo = MetricsRepository(settings)

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            await log_repo.write_request_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": get_client_ip(request, settings.trust_proxy),
                    "user_agent": request.headers.get("user-agent", "")[:200],
                    "error": str(exc),
                }
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if hasattr(request.state, "rate_limit_limit"):
            response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
            response.headers["X-RateLimit-Remaining"] = str(getattr(request.state, "rate_limit_remaining", 0))

        if response.status_code == 429:
            await metrics_repo.record_rate_limited()

        await log_repo.write_request_log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": get_client_ip(request, settings.trust_proxy),
                "user_agent": request.headers.get("user-agent", "")[:200],
                "error": None,
            }
        )

        response.headers["X-Request-Id"] = request_id
        return response
