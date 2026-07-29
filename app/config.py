from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Contact API"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    trust_proxy: bool = False
    max_request_body_bytes: int = 32_768

    data_dir: Path = Path("./data")

    rate_limit_max_requests: int = 5
    rate_limit_window_seconds: int = 3600

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    owner_email: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 5

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    ai_timeout_seconds: int = 8
    # auto = groq → gemini → openai (только настроенные)
    ai_provider: str = "auto"

    metrics_api_key: str = ""

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from and self.owner_email)

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def ai_provider_chain(self) -> list[str]:
        if self.ai_provider != "auto":
            return [self.ai_provider]

        chain: list[str] = []
        if self.groq_configured:
            chain.append("groq")
        if self.gemini_configured:
            chain.append("gemini")
        if self.openai_configured:
            chain.append("openai")
        return chain

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def rate_limit_dir(self) -> Path:
        return self.data_dir / "rate_limit"

    @property
    def metrics_file(self) -> Path:
        return self.data_dir / "metrics.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
