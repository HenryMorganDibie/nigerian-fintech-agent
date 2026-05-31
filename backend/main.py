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
    description=(
        "Production AI agent for Nigerian fintechs — "
        "7-layer fraud intelligence, Bayesian scoring, behavioral memory, "
        "fraud graph, A/B testing, case queue, drift monitoring."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.github\.io",
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
        "circuit_breakers": get_circuit_breaker_status(),
        "token_budget": token_budget.get_status(),
    }


@app.get("/api/providers")
async def providers():
    return {
        "providers": get_available_providers(),
        "default": settings.default_llm_provider,
    }
