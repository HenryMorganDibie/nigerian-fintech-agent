from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Literal
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    cors_origins: str | list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://henrymorgandibie.github.io",
    ]

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_api_key: str = ""
    google_model: str = "gemini-1.5-pro"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    default_llm_provider: Literal["openai", "anthropic", "google", "groq"] = "groq"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return [o.rstrip("/") for o in v]
        return v

    model_config = {"env_file": str(ENV_FILE), "extra": "ignore"}


settings = Settings()


def get_available_providers() -> list[dict]:
    providers = []
    if settings.groq_api_key:
        providers.append({"id": "groq", "name": "Groq (Free)", "model": settings.groq_model})
    if settings.openai_api_key:
        providers.append({"id": "openai", "name": "OpenAI GPT-4o", "model": settings.openai_model})
    if settings.anthropic_api_key:
        providers.append({"id": "anthropic", "name": "Anthropic Claude", "model": settings.anthropic_model})
    if settings.google_api_key:
        providers.append({"id": "google", "name": "Google Gemini", "model": settings.google_model})
    return providers


def validate_startup():
    print("\n── NaijaFinAI Startup Check ──────────────────")
    print(f"  .env path       : {ENV_FILE}")
    print(f"  Default provider: {settings.default_llm_provider}")
    print(f"  CORS origins    : {settings.cors_origins}")
    keys = {
        "groq":      settings.groq_api_key,
        "openai":    settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google":    settings.google_api_key,
    }
    for name, key in keys.items():
        status = "✅ ready" if key else "⚠️  not set"
        print(f"  {name:<12}: {status}")
    active = keys.get(settings.default_llm_provider, "")
    if not active:
        print(f"\n  ❌ ERROR: DEFAULT_LLM_PROVIDER='{settings.default_llm_provider}' but key is empty!")
        print(f"     → Set {settings.default_llm_provider.upper()}_API_KEY in Railway environment variables\n")
    else:
        print(f"\n  ✅ Ready — {settings.default_llm_provider.upper()} / {getattr(settings, settings.default_llm_provider + '_model')}\n")
    print("──────────────────────────────────────────────\n")
