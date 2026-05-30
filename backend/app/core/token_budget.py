"""
Token Budget Manager
=====================
Tracks daily LLM token usage per provider.
Estimates tokens before calls and decides which model to use.
Prevents 429 loops by proactively switching models.

Daily limits (Groq free tier):
  llama-3.3-70b-versatile: 100,000 tokens/day
  llama-3.1-8b-instant:    500,000 tokens/day
"""

from datetime import datetime, timezone, date
from collections import defaultdict
from dataclasses import dataclass, field
import threading
import math

# Groq free tier daily limits (tokens)
DAILY_LIMITS = {
    "groq_primary":  100_000,
    "groq_fallback": 500_000,
    "openai":        999_999_999,  # paid — no practical limit
    "anthropic":     999_999_999,
}

# Approximate tokens per character (rough estimate)
CHARS_PER_TOKEN = 4

# Reserve buffer — switch model when this % remains
RESERVE_PCT = 0.15  # switch when 15% remains


@dataclass
class ProviderUsage:
    provider: str
    date: str = field(default_factory=lambda: date.today().isoformat())
    tokens_used: int = 0
    calls_made: int = 0
    calls_skipped: int = 0


class TokenBudgetManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._usage: dict[str, ProviderUsage] = {}

    def _today(self) -> str:
        return date.today().isoformat()

    def _get(self, provider: str) -> ProviderUsage:
        today = self._today()
        key = f"{provider}:{today}"
        if key not in self._usage or self._usage[key].date != today:
            self._usage[key] = ProviderUsage(provider=provider, date=today)
        return self._usage[key]

    def estimate_tokens(self, prompt: str, expected_output_chars: int = 200) -> int:
        """Rough token estimate from character count."""
        return math.ceil((len(prompt) + expected_output_chars) / CHARS_PER_TOKEN)

    def record_usage(self, provider: str, tokens: int):
        with self._lock:
            usage = self._get(provider)
            usage.tokens_used += tokens
            usage.calls_made += 1

    def get_remaining(self, provider: str) -> int:
        usage = self._get(provider)
        limit = DAILY_LIMITS.get(provider, 999_999_999)
        return max(0, limit - usage.tokens_used)

    def get_remaining_pct(self, provider: str) -> float:
        limit = DAILY_LIMITS.get(provider, 999_999_999)
        remaining = self.get_remaining(provider)
        return remaining / limit if limit > 0 else 1.0

    def should_use_large_model(self, prompt: str, provider: str = "groq_primary") -> bool:
        """
        Returns True if it's safe to use the large (primary) model.
        False means use fallback or rules-only.
        """
        remaining_pct = self.get_remaining_pct(provider)
        if remaining_pct < RESERVE_PCT:
            return False
        estimated = self.estimate_tokens(prompt)
        remaining = self.get_remaining(provider)
        return estimated < remaining

    def pick_model(self, prompt: str, importance: str = "medium") -> str:
        """
        Pick the appropriate model based on token budget and call importance.
        importance: 'high' (critical fraud), 'medium' (explanation), 'low' (chat)
        """
        primary_ok = self.should_use_large_model(prompt, "groq_primary")
        fallback_ok = self.should_use_large_model(prompt, "groq_fallback")

        if importance == "low":
            # Always use small model for low-importance calls
            return "groq_fallback"
        elif importance == "high" and primary_ok:
            return "groq_primary"
        elif fallback_ok:
            return "groq_fallback"
        else:
            # Both exhausted — use rules only
            return "rules_only"

    def get_status(self) -> dict:
        today = self._today()
        result = {}
        for provider in ["groq_primary", "groq_fallback", "openai", "anthropic"]:
            usage = self._get(provider)
            limit = DAILY_LIMITS.get(provider, 999_999_999)
            remaining = self.get_remaining(provider)
            result[provider] = {
                "date": today,
                "tokens_used": usage.tokens_used,
                "tokens_remaining": remaining,
                "daily_limit": limit if limit < 999_999_999 else "unlimited",
                "remaining_pct": round(self.get_remaining_pct(provider) * 100, 1),
                "calls_made": usage.calls_made,
                "status": "ok" if self.get_remaining_pct(provider) > RESERVE_PCT else "reserve_mode",
            }
        return result


# Singleton
token_budget = TokenBudgetManager()
