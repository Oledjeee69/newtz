import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings

DEFAULT_METRICS: dict[str, Any] = {
    "total_contacts": 0,
    "by_request_type": {},
    "by_sentiment": {},
    "ai_fallback_count": 0,
    "rate_limited_count": 0,
    "contacts_by_day": {},
}


class MetricsRepository:
    def __init__(self, settings: Settings):
        self._path = settings.metrics_file
        self._settings = settings
        self._ensure_file()

    def _ensure_file(self) -> None:
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(json.dumps(DEFAULT_METRICS, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_METRICS.copy()

    def _write(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def record_contact(
        self,
        request_type: str | None,
        sentiment: str | None,
        ai_fallback: bool,
    ) -> None:
        data = self._read()
        data["total_contacts"] = data.get("total_contacts", 0) + 1

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        by_day: dict[str, int] = data.setdefault("contacts_by_day", {})
        by_day[today] = by_day.get(today, 0) + 1

        if request_type:
            types: dict[str, int] = data.setdefault("by_request_type", {})
            types[request_type] = types.get(request_type, 0) + 1

        if sentiment:
            sentiments: dict[str, int] = data.setdefault("by_sentiment", {})
            sentiments[sentiment] = sentiments.get(sentiment, 0) + 1

        if ai_fallback:
            data["ai_fallback_count"] = data.get("ai_fallback_count", 0) + 1

        self._write(data)

    async def record_rate_limited(self) -> None:
        data = self._read()
        data["rate_limited_count"] = data.get("rate_limited_count", 0) + 1
        self._write(data)

    async def get_metrics(self) -> dict[str, Any]:
        data = self._read()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "total_contacts": data.get("total_contacts", 0),
            "today": data.get("contacts_by_day", {}).get(today, 0),
            "by_request_type": data.get("by_request_type", {}),
            "by_sentiment": data.get("by_sentiment", {}),
            "ai_fallback_count": data.get("ai_fallback_count", 0),
            "rate_limited_count": data.get("rate_limited_count", 0),
        }
