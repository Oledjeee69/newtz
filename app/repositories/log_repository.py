import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings


class LogRepository:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self._settings.logs_dir.mkdir(parents=True, exist_ok=True)

    def _log_file(self, prefix: str) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._settings.logs_dir / f"{prefix}-{date}.jsonl"

    async def write_request_log(self, entry: dict[str, Any]) -> None:
        await self._append(self._log_file("requests"), entry)

    async def write_error_log(self, entry: dict[str, Any]) -> None:
        await self._append(self._log_file("errors"), entry)

    async def _append(self, path: Path, entry: dict[str, Any]) -> None:
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
