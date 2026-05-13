from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.core.llm_factory import get_llm
from app.core.prompts import BASE_SYSTEM_PROMPT
from app.core.language import detect_language, LANGUAGE_INSTRUCTIONS, enrich_context_with_glossary
from app.core.compliance import AuditLogEntry
from app.tools.fintech_tools import AGENT_TOOLS
from app.models.schemas import ChatMessage
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
import json, hashlib, uuid


def _make_audit(provider: str, event: str = "chat_interaction") -> AuditLogEntry:
    retention = (datetime.now(timezone.utc) + timedelta(days=365 * 5)).isoformat()
    return AuditLogEntry(
        event_type=event,
        llm_provider=provider,
        data_retention_expires=retention,
    )


def _build_prompt(language: str) -> ChatPromptTemplate:
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, "")
    system = BASE_SYSTEM_PROMPT
    if lang_instruction:
        system += f"\n\n## Language Instruction\n{lang_instruction}"
    return ChatPromptTemplate.from_messages([
        ("system", system),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])


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
    """Returns (reply, provider_used, tool_calls, language, audit_id)"""
    provider = provider or settings.default_llm_provider
    language = detect_language(message)
    enriched = enrich_context_with_glossary(message)

    llm = get_llm(provider=provider)
    prompt = _build_prompt(language)
    audit = _make_audit(provider)

    agent = create_tool_calling_agent(llm, AGENT_TOOLS, prompt)
    executor = AgentExecutor(
        agent=agent, tools=AGENT_TOOLS,
        verbose=False, return_intermediate_steps=True,
        max_iterations=5, handle_parsing_errors=True,
    )

    result = executor.invoke({"input": enriched, "chat_history": _to_lc_history(history)})
    reply = result.get("output", "I encountered an issue. Please try again.")
    tool_calls = [
        step[0].tool for step in result.get("intermediate_steps", [])
        if hasattr(step[0], "tool")
    ]
    return reply, provider, tool_calls, language, audit.audit_id


async def run_agent_stream(
    message: str,
    history: list[ChatMessage],
    provider: str | None = None,
) -> AsyncGenerator[str, None]:
    provider = provider or settings.default_llm_provider
    language = detect_language(message)

    yield f"data: {json.dumps({'type': 'language', 'language': language})}\n\n"

    reply, _, tool_calls, _, audit_id = run_agent(message, history, provider)

    if tool_calls:
        yield f"data: {json.dumps({'type': 'tool_calls', 'tools': tool_calls})}\n\n"

    chunk_size = 10
    for i in range(0, len(reply), chunk_size):
        yield f"data: {json.dumps({'type': 'token', 'content': reply[i:i+chunk_size]})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'provider': provider, 'audit_id': audit_id})}\n\n"
