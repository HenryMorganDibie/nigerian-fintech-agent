from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, get_available_providers, validate_startup
from app.routers import chat, fraud, loans, transactions, eval, workflows, media

validate_startup()

app = FastAPI(
    title="NaijaFinAI Agent API",
    description="Production-grade AI agent for Nigerian fintechs.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.github\.io",  # covers all GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(fraud.router)
app.include_router(loans.router)
app.include_router(transactions.router)
app.include_router(eval.router)
app.include_router(workflows.router)
app.include_router(media.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "NaijaFinAI Agent", "version": "3.0.0"}


@app.get("/api/providers")
async def providers():
    return {
        "providers": get_available_providers(),
        "default": settings.default_llm_provider,
    }
