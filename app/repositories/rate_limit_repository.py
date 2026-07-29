import hashlib
import json
import time
from pathlib import Path

from app.config import Settings
from app.core.exceptions import RateLimitError


class RateLimitRepository:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._dir = settings.rate_limit_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, client_ip: str) -> Path:
        digest = hashlib.sha256(client_ip.encode()).hexdigest()
        return self._dir / f"{digest}.json"

    def _cleanup_old(self) -> None:
        cutoff = time.time() - 86400
        for path in self._dir.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    async def check_and_increment(self, client_ip: str) -> None:
        self._cleanup_old()
        path = self._key_path(client_ip)
        now = time.time()
        window = self._settings.rate_limit_window_seconds
        max_requests = self._settings.rate_limit_max_requests

        timestamps: list[float] = []
        if path.exists():
            try:
                timestamps = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                timestamps = []

        timestamps = [t for t in timestamps if now - t < window]

        if len(timestamps) >= max_requests:
            oldest = min(timestamps) if timestamps else now
            retry_after = max(1, int(window - (now - oldest)))
            raise RateLimitError(retry_after=retry_after)

        timestamps.append(now)
        path.write_text(json.dumps(timestamps), encoding="utf-8")

    def remaining(self, client_ip: str) -> int:
        path = self._key_path(client_ip)
        now = time.time()
        window = self._settings.rate_limit_window_seconds
        max_requests = self._settings.rate_limit_max_requests

        if not path.exists():
            return max_requests

        try:
            timestamps = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return max_requests

        active = [t for t in timestamps if now - t < window]
        return max(0, max_requests - len(active))
