from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FinWiseAI"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = (
        f"sqlite:///{(BACKEND_ROOT / 'vantageai.db').as_posix()}"
    )

    frontend_origin: str = "http://localhost:3000"

    openrouter_api_key: str = ""
    openrouter_model: str = ""
    alpha_vantage_api_key: str = ""
    evaluation_update_token: str = ""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
