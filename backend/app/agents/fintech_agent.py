"""
NaijaFinAI Agent — LangChain 1.x compatible
Uses bind_tools + manual tool-call loop (no AgentExecutor needed).
Works on LangChain >=0.3 and 1.x.
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.core.llm_factory import get_llm
from app.core.prompts import BASE_SYSTEM_PROMPT
from app.core.language import detect_language, LANGUAGE_INSTRUCTIONS, enrich_context_with_glossary
from app.core.compliance import AuditLogEntry
from app.tools.fintech_tools import AGENT_TOOLS, nigerian_fraud_score, cbn_loan_eligibility, naija_spending_insights
from app.models.schemas import ChatMessage
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
import json, uuid

# Tool name -> callable map
TOOL_MAP = {
    "nigerian_fraud_score":   nigerian_fraud_score,
    "cbn_loan_eligibility":   cbn_loan_eligibility,
    "naija_spending_insights": naija_spending_insights,
}


def _make_audit(provider: str) -> AuditLogEntry:
    return AuditLogEntry(
        event_type="chat_interaction",
        llm_provider=provider,
        data_retention_expires=(
            datetime.now(timezone.utc) + timedelta(days=365 * 5)
        ).isoformat(),
    )


def _build_system(language: str) -> str:
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, "")
    system = BASE_SYSTEM_PROMPT
    if lang_instruction:
        system += f"\n\n## Language Instruction\n{lang_instruction}"
    return system


def _to_lc_history(history: list[ChatMessage]) -> list:
    out = []
    for m in history:
        if m.role == "user":
            out.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content))
    return out


def run_agent(
    message: str,
    history: list[ChatMessage],
    provider: str | None = None,
) -> tuple[str, str, list[str], str, str]:
    """Returns (reply, provider, tool_calls, language, audit_id)"""
    provider = provider or settings.default_llm_provider
    language = detect_language(message)
    enriched = enrich_context_with_glossary(message)
    audit = _make_audit(provider)

    llm = get_llm(provider=provider)
    llm_with_tools = llm.bind_tools(AGENT_TOOLS)

    messages = [
        SystemMessage(content=_build_system(language)),
        *_to_lc_history(history),
        HumanMessage(content=enriched),
    ]

    tool_calls_made = []

    # Tool-call loop — max 5 iterations
    for _ in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # No tool calls — we have the final answer
        if not getattr(response, "tool_calls", None):
            break

        # Execute each tool call
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id   = tc.get("id", str(uuid.uuid4()))
            tool_calls_made.append(tool_name)

            tool_fn = TOOL_MAP.get(tool_name)
            if tool_fn:
                try:
                    result = tool_fn.invoke(tool_args)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
            else:
                result = json.dumps({"error": f"Unknown tool: {tool_name}"})

            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

    reply = response.content if hasattr(response, "content") else "I encountered an issue. Please try again."
    return reply, provider, tool_calls_made, language, audit.audit_id


async def run_agent_stream(
    message: str,
    history: list[ChatMessage],
    provider: str | None = None,
) -> AsyncGenerator[str, None]:
    provider = provider or settings.default_llm_provider
    language = detect_language(message)

    yield f"data: {json.dumps({'type': 'language', 'language': language})}\n\n"

    try:
        reply, _, tool_calls, _, audit_id = run_agent(message, history, provider)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'token', 'content': f'Error: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'provider': provider, 'audit_id': ''})}\n\n"
        return

    if tool_calls:
        yield f"data: {json.dumps({'type': 'tool_calls', 'tools': tool_calls})}\n\n"

    chunk_size = 10
    for i in range(0, len(reply), chunk_size):
        yield f"data: {json.dumps({'type': 'token', 'content': reply[i:i+chunk_size]})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'provider': provider, 'audit_id': audit_id})}\n\n"
