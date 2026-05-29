"""
LLM Factory with Groq dual-model fallback.
Primary: llama-3.3-70b-versatile
Fallback: llama3-70b-8192 (when primary hits rate limit)
Both are free on Groq.
"""

from langchain_core.language_models import BaseChatModel
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_llm(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    provider = provider or settings.default_llm_provider

    if provider in ("groq", "groq_fast"):
        return _get_groq_llm(streaming=streaming, use_fallback=(provider == "groq_fast"))

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key,
                          streaming=streaming, temperature=0.1)

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.anthropic_model, api_key=settings.anthropic_api_key,
                             streaming=streaming, temperature=0.1)

    elif provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=settings.google_model,
                                          google_api_key=settings.google_api_key,
                                          streaming=streaming, temperature=0.1)
        except ImportError:
            raise ValueError("Google provider not installed")

    raise ValueError(f"Unknown provider: {provider}")


def _get_groq_llm(streaming: bool = False, use_fallback: bool = False) -> BaseChatModel:
    from langchain_groq import ChatGroq
    model = settings.groq_fallback_model if use_fallback else settings.groq_model
    return ChatGroq(model=model, api_key=settings.groq_api_key,
                    streaming=streaming, temperature=0.1)


def get_llm_with_fallback(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    """
    Returns primary LLM. If it's Groq and hits rate limit (429),
    automatically falls back to the secondary Groq model.
    Use this for all agent calls.
    """
    provider = provider or settings.default_llm_provider
    try:
        return get_llm(provider=provider, streaming=streaming)
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            logger.warning(f"Groq rate limit hit on {settings.groq_model} — falling back to {settings.groq_fallback_model}")
            return _get_groq_llm(streaming=streaming, use_fallback=True)
        raise
