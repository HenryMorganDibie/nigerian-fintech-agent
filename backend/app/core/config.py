from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Literal
from pathlib import Path

# Always resolve .env relative to this file's location (backend/)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    # Accepts both a Python list and a comma-separated string from .env
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    default_llm_provider: Literal["openai", "anthropic", "google", "groq"] = "openai"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = {"env_file": str(ENV_FILE), "extra": "ignore"}


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


def validate_startup():
    """Call on app startup — prints a clear status of which providers are ready."""
    print("\n── NaijaFinAI Startup Check ──────────────────")
    print(f"  .env loaded from : {ENV_FILE}")
    print(f"  Default provider : {settings.default_llm_provider}")
    keys = {
        "openai":    settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google":    settings.google_api_key,
        "groq":      settings.groq_api_key,
    }
    for name, key in keys.items():
        status = "✅ ready" if key else "⚠️  not set"
        print(f"  {name:<12}: {status}")

    active = keys.get(settings.default_llm_provider, "")
    if not active:
        print(f"\n  ❌ ERROR: DEFAULT_LLM_PROVIDER is '{settings.default_llm_provider}' but its API key is empty!")
        print(f"     → Set {settings.default_llm_provider.upper()}_API_KEY in your .env file\n")
    else:
        print(f"\n  ✅ Ready — using {settings.default_llm_provider.upper()}\n")
    print("──────────────────────────────────────────────\n")
