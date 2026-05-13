from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    api_key_header: str = "X-API-Key"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    default_llm_provider: Literal["openai", "anthropic", "google", "groq"] = "openai"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def get_available_providers() -> list[dict]:
    providers = []
    if settings.openai_api_key:
        providers.append({"id": "openai", "name": "OpenAI GPT-4o", "model": "gpt-4o"})
    if settings.anthropic_api_key:
        providers.append({"id": "anthropic", "name": "Anthropic Claude", "model": "claude-sonnet-4-20250514"})
    if settings.google_api_key:
        providers.append({"id": "google", "name": "Google Gemini", "model": "gemini-1.5-pro"})
    if settings.groq_api_key:
        providers.append({"id": "groq", "name": "Groq LLaMA", "model": "llama-3.3-70b-versatile"})
    return providers
