import traceback
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.schemas.contact import FIELD_LABELS
from app.core.exceptions import AppError, RateLimitError
from app.repositories.log_repository import LogRepository


def register_error_handlers(app: FastAPI) -> None:
    settings = get_settings()
    log_repo = LogRepository(settings)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        headers = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)

        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.code, "message": exc.message}},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
            raw_msg = err.get("msg", "Invalid value")
            if raw_msg.startswith("Value error, "):
                raw_msg = raw_msg.removeprefix("Value error, ")
            if loc == "comment" and "at least 10" in raw_msg:
                raw_msg = "Комментарий должен быть не короче 10 символов"
            label = FIELD_LABELS.get(loc, loc)
            errors.append({"field": loc, "message": raw_msg, "label": label})
        summary = "; ".join(f"{e['label']}: {e['message']}" for e in errors) or "Ошибка валидации"
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {"code": "validation_error", "message": summary, "details": errors},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": "http_error", "message": exc.detail},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        await log_repo.write_error_log(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url.path),
                "method": request.method,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "internal_error", "message": "Внутренняя ошибка сервера"},
            },
        )
