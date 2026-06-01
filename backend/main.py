from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, get_available_providers, validate_startup
from app.core.llm_factory import get_circuit_breaker_status
from app.routers import (
    chat, fraud, loans, transactions,
    eval, workflows, media,
    ab_testing, simulation, cases,
)

validate_startup()

app = FastAPI(
    title="NaijaFinAI Agent API",
    description="Production AI agent for Nigerian fintechs.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Build CORS origins — always include GitHub Pages regardless of env var
_origins = list(settings.cors_origins) if settings.cors_origins else []
_always_allowed = [
    "https://henrymorgandibie.github.io",
    "http://localhost:5173",
    "http://localhost:3000",
]
for o in _always_allowed:
    if o not in _origins:
        _origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.github\.io",  # covers all GitHub Pages subpaths
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [chat, fraud, loans, transactions, eval, workflows, media, ab_testing, simulation, cases]:
    app.include_router(r.router)


@app.get("/api/health")
async def health():
    from app.core.token_budget import token_budget
    return {
        "status": "ok",
        "service": "NaijaFinAI Agent",
        "version": "3.0.0",
        "cors_origins": _origins,
        "circuit_breakers": get_circuit_breaker_status(),
        "token_budget": token_budget.get_status(),
    }


@app.get("/api/providers")
async def providers():
    return {
        "providers": get_available_providers(),
        "default": settings.default_llm_provider,
    }
