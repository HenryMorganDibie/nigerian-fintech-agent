from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.agents.fintech_agent import run_agent, run_agent_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.stream:
        return StreamingResponse(
            run_agent_stream(req.message, req.history, req.provider),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    reply, provider, tool_calls, language, audit_id = run_agent(req.message, req.history, req.provider)
    return ChatResponse(reply=reply, provider_used=provider, tool_calls=tool_calls,
                        language_detected=language, audit_id=audit_id)
