from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./carpass.db"
    secret_key: str = "change-me-in-production-carpass-oman-2026"
    openai_api_key: str = ""
    scraping_proxy_url: str = ""
    ais_api_key: str = ""
    ais_api_url: str = "https://api.datalastic.com/api/v0/vessel_inradius"
    exchange_rate_api: str = "https://open.er-api.com/v6/latest/USD"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    access_token_expire_minutes: int = 60 * 24 * 7

    # Oman customs defaults
    customs_duty_rate: float = 0.05
    vat_rate: float = 0.05

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
