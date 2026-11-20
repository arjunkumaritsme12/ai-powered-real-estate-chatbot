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
    gemini_api_key: str = ""
    gemini_model: str = "gemini-4-hydrogen"
    gemini_fallback_models: str = "gemini-3.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    ai_provider: str = "gemini"
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

    @property
    def gemini_model_list(self) -> list[str]:
        values = [self.gemini_model]
        values.extend(item.strip() for item in self.gemini_fallback_models.split(",") if item.strip())
        return list(dict.fromkeys(values))

    @property
    def provider_list(self) -> list[str]:
        preferred = self.ai_provider.strip().lower()
        if preferred not in {"gemini", "openrouter"}:
            preferred = "gemini"
        other = "openrouter" if preferred == "gemini" else "gemini"
        return [preferred, other]


@lru_cache
def get_settings() -> Settings:
    return Settings()
