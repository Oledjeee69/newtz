import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import contact, health, metrics
from app.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.middleware.request_logger import RequestLoggingMiddleware
from app.middleware.security import SecurityMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.rate_limit_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Started %s v%s", settings.app_name, settings.app_version)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API формы обратной связи: валидация, почта, разбор комментария, метрики.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    register_error_handlers(app)

    app.include_router(contact.router)
    app.include_router(health.router)
    app.include_router(metrics.router)

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def landing():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
