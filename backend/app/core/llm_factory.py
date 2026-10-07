"""
Backwards-compatible entry points over the rotating router in llm_router.py.

Previously get_llm_with_fallback() only constructed the first client and never
called it, so a 429 at call time was never failed over. Every function here now
returns a RoutedChatModel: each call walks the health-aware chain
(Ollama pool / Groq models / OpenAI / Anthropic) and fails over for real.
"""

from langchain_core.language_models import BaseChatModel

from app.core.llm_router import Profile, get_routed_llm, get_router


def get_llm(provider: str | None = None, streaming: bool = False, profile: Profile = "interactive") -> BaseChatModel:
    """`provider`, when explicitly chosen, is tried first; the rest of the chain still backs it up."""
    return get_routed_llm(provider, profile)


def get_llm_with_fallback(provider: str | None = None, streaming: bool = False,
                          profile: Profile = "interactive") -> BaseChatModel:
    return get_routed_llm(provider, profile)


def get_circuit_breaker_status() -> dict:
    """Per-candidate health and cooldowns for both router profiles (kept under the old name for /api/health)."""
    out = {}
    for profile in ("interactive", "batch"):
        try:
            out[profile] = get_router(profile).status()
        except RuntimeError as exc:
            out[profile] = {"error": str(exc)}
    return out
