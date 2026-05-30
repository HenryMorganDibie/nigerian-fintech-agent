from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, get_available_providers, validate_startup
from app.core.llm_factory import get_circuit_breaker_status
from app.routers import chat, fraud, loans, transactions, eval, workflows, media, ab_testing, simulation

validate_startup()

app = FastAPI(
    title="NaijaFinAI Agent API",
    description="Production AI agent for Nigerian fintechs — 7-layer fraud intelligence, explainability, circuit breaker, A/B testing, simulation sandbox.",
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

for router in [chat, fraud, loans, transactions, eval, workflows, media, ab_testing, simulation]:
    app.include_router(router.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "NaijaFinAI Agent",
        "version": "3.0.0",
        "circuit_breakers": get_circuit_breaker_status(),
    }


@app.get("/api/providers")
async def providers():
    return {"providers": get_available_providers(), "default": settings.default_llm_provider}
