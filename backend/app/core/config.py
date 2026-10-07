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
    anthropic_model: str = "claude-opus-5-5"
    google_api_key: str = ""
    google_model: str = "gemini-1.5-pro"

    default_llm_provider: Literal["openai", "anthropic", "google", "groq", "ollama"] = "groq"

    # ── LLM rotation (see app/core/llm_router.py) ──────────────────────────
    # Comma-separated, strongest first. Empty = gpt-oss-120b, gpt-oss-20b,
    # then GROQ_MODEL and GROQ_FALLBACK_MODEL.
    groq_models: str = ""
    # Optional OpenAI-compatible gateway in front of Groq. Empty = api.groq.com.
    groq_base_url: str = ""
    # Local Ollama pool. Empty disables it.
    ollama_base_url: str = "http://127.0.0.1:11434"
    # first | last | off | only  ("only" = on-machine models only, for data residency)
    llm_local_pool: Literal["first", "last", "off", "only"] = "last"
    ollama_min_quality: float = 0.5
    ollama_timeout_s: float = 30.0
    llm_timeout_s: float = 20.0

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
    """Choices for the UI provider picker. Picking one moves it to the front of the rotation."""
    from app.core.llm_router import groq_model_order
    providers = []
    if settings.groq_api_key:
        providers.append({"id": "groq", "name": f"Groq ({', '.join(groq_model_order())})",
                          "model": groq_model_order()[0]})
    if settings.openai_api_key:
        providers.append({"id": "openai",    "name": f"OpenAI {settings.openai_model}", "model": settings.openai_model})
    if settings.anthropic_api_key:
        providers.append({"id": "anthropic", "name": f"Anthropic {settings.anthropic_model}", "model": settings.anthropic_model})
    if settings.google_api_key:
        providers.append({"id": "google",    "name": f"Google {settings.google_model}", "model": settings.google_model})
    if settings.ollama_base_url and settings.llm_local_pool != "off":
        providers.append({"id": "ollama", "name": "Local Ollama pool (fastest healthy model)", "model": "auto"})
    return providers


def validate_startup():
    print("\n── NaijaFinAI v3 Startup Check ──────────────────")
    print(f"  .env path        : {ENV_FILE}")
    print(f"  Default provider : {settings.default_llm_provider}")
    print(f"  CORS origins     : {settings.cors_origins}")
    print(f"  LLM local pool   : {settings.llm_local_pool}")
    print(f"  Feature store    : {'Redis @ ' + settings.redis_url if settings.redis_url else 'In-memory (no Redis URL set)'}")
    keys = {
        "groq":      settings.groq_api_key,
        "openai":    settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google":    settings.google_api_key,
    }
    for name, key in keys.items():
        print(f"  {name:<12}: {'✅ ready' if key else '⚠️  not set'}")
    pool = settings.llm_local_pool if settings.ollama_base_url else "off"
    print(f"  ollama pool : {pool}" + (f" @ {settings.ollama_base_url}" if pool != "off" else ""))
    if not any(keys.values()) and pool == "off":
        print("\n  ❌ No LLM provider configured: chat and narratives will be unavailable.")
        print("     → Set GROQ_API_KEY (free), ANTHROPIC_API_KEY, or OLLAMA_BASE_URL\n")
    else:
        print("\n  ✅ LLM rotation ready (see /api/health → llm)\n")
    db_kind = settings.database_url.split(":", 1)[0]
    print(f"  Database         : {db_kind}")
    print(f"  Demo sandbox     : {'mounted at /api' if settings.demo_mode else 'disabled'}")
    print(f"  Admin API        : {'enabled' if settings.admin_token else 'disabled (ADMIN_TOKEN not set)'}")
    if settings.app_env == "production" and settings.secret_key == "dev-secret-key":
        print("  ❌ SECRET_KEY is the development default. Set a random SECRET_KEY before taking traffic.")
    print("─────────────────────────────────────────────────\n")
