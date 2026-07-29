from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.contact import MetricsResponse

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(x_metrics_key: str | None = Header(default=None, alias="X-Metrics-Key")) -> MetricsResponse:
    settings = get_settings()

    if not settings.metrics_api_key:
        if not settings.debug:
            raise HTTPException(status_code=403, detail="Metrics endpoint disabled. Set METRICS_API_KEY.")
    elif x_metrics_key != settings.metrics_api_key:
        raise HTTPException(status_code=401, detail="Invalid metrics key")

    repo = MetricsRepository(settings)
    data = await repo.get_metrics()
    return MetricsResponse(**data)
