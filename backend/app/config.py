from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "PropertyIQ"
    app_env: str = "development"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    openrouter_fallback_models: str = "nvidia/nemotron-3.5-lightning:free,google/gemma-4-31b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: int = 30
    admin_token: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    data_dir: str = str(Path(__file__).resolve().parents[1] / "data")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    scrape_rate_limit_seconds: float = 1.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def model_list(self) -> list[str]:
        values = [self.openrouter_model]
        values.extend(item.strip() for item in self.openrouter_fallback_models.split(",") if item.strip())
        return list(dict.fromkeys(values))


@lru_cache
def get_settings() -> Settings:
    return Settings()
