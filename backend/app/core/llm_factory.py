from langchain_core.language_models import BaseChatModel
from app.core.config import settings


def get_llm(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    provider = provider or settings.default_llm_provider

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key, streaming=streaming, temperature=0.1)

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-20250514", api_key=settings.anthropic_api_key, streaming=streaming, temperature=0.1)

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=settings.google_api_key, streaming=streaming, temperature=0.1)

    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key, streaming=streaming, temperature=0.1)

    raise ValueError(f"Unknown provider: {provider}")
