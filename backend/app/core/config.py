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

    # ── Groq — primary + fallback (both free) ──────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "llama-3.1-8b-instant"   # fallback when primary hits rate limit

    # ── Optional providers ─────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    google_api_key: str = ""
    google_model: str = "gemini-1.5-pro"

    default_llm_provider: Literal["openai", "anthropic", "google", "groq"] = "groq"

    # ── Feature store (in-memory by default, Redis if URL provided) ────────
    redis_url: str = ""

    # ── Persistence ────────────────────────────────────────────────────────
    # SQLite for local dev; set a postgresql+psycopg:// URL in production.
    database_url: str = "sqlite:///./naijafinai.db"

    # ── Platform / multi-tenancy ───────────────────────────────────────────
    # Bootstrap token for /v1/admin. Leave empty to disable the admin API.
    admin_token: str = ""
    # Keeps the open /api/* sandbox (used by the public demo UI) mounted.
    # Set DEMO_MODE=false for a customer deployment so only /v1 is exposed.
    demo_mode: bool = True
    # Default mode for newly created tenants: score but never enforce.
    default_tenant_mode: Literal["shadow", "live"] = "shadow"
    # Bump whenever scoring logic or signal parameters change.
    model_version: str = "rules-2026.10.0"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return [o.rstrip("/") for o in v]
        return v

    model_config = {"env_file": str(ENV_FILE), "extra": "ignore", "protected_namespaces": ("settings_",)}


settings = Settings()


def get_available_providers() -> list[dict]:
    providers = []
    if settings.groq_api_key:
        providers.append({"id": "groq",      "name": "Groq LLaMA-3.3-70B (Free)", "model": settings.groq_model})
        providers.append({"id": "groq_fast", "name": "Groq LLaMA-3-70B (Fallback)", "model": settings.groq_fallback_model})
    if settings.openai_api_key:
        providers.append({"id": "openai",    "name": "OpenAI GPT-4o",  "model": settings.openai_model})
    if settings.anthropic_api_key:
        providers.append({"id": "anthropic", "name": "Claude Sonnet",  "model": settings.anthropic_model})
    if settings.google_api_key:
        providers.append({"id": "google",    "name": "Gemini 1.5 Pro", "model": settings.google_model})
    return providers


def validate_startup():
    print("\n── NaijaFinAI v3 Startup Check ──────────────────")
    print(f"  .env path        : {ENV_FILE}")
    print(f"  Default provider : {settings.default_llm_provider}")
    print(f"  CORS origins     : {settings.cors_origins}")
    print(f"  Groq primary     : {settings.groq_model}")
    print(f"  Groq fallback    : {settings.groq_fallback_model}")
    print(f"  Feature store    : {'Redis @ ' + settings.redis_url if settings.redis_url else 'In-memory (no Redis URL set)'}")
    keys = {
        "groq":      settings.groq_api_key,
        "openai":    settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google":    settings.google_api_key,
    }
    for name, key in keys.items():
        print(f"  {name:<12}: {'✅ ready' if key else '⚠️  not set'}")
    active = keys.get(settings.default_llm_provider, "")
    if not active:
        print(f"\n  ❌ ERROR: DEFAULT_LLM_PROVIDER='{settings.default_llm_provider}' but key is empty!")
        print(f"     → Set {settings.default_llm_provider.upper()}_API_KEY in Railway environment variables\n")
    else:
        print(f"\n  ✅ Ready — {settings.default_llm_provider.upper()} / {settings.groq_model}\n")
    db_kind = settings.database_url.split(":", 1)[0]
    print(f"  Database         : {db_kind}")
    print(f"  Demo sandbox     : {'mounted at /api' if settings.demo_mode else 'disabled'}")
    print(f"  Admin API        : {'enabled' if settings.admin_token else 'disabled (ADMIN_TOKEN not set)'}")
    if settings.app_env == "production" and settings.secret_key == "dev-secret-key":
        print("  ❌ SECRET_KEY is the development default. Set a random SECRET_KEY before taking traffic.")
    print("─────────────────────────────────────────────────\n")
