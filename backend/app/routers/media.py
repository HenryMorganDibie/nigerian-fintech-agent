"""
Voice & File Upload Router
===========================
Voice: Groq Whisper (free) — transcribes all Nigerian languages
File:  PDF/image/CSV/TXT — extracts text, scans for fraud signals
"""

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.core.language import detect_language, enrich_context_with_glossary
from app.core.config import settings
from app.core.llm_factory import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
import tempfile, os, json

router = APIRouter(prefix="/api/media", tags=["voice & files"])

SUPPORTED_AUDIO = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}
SUPPORTED_DOCS  = {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".txt"}


@router.post("/voice")
async def transcribe_voice(
    file: UploadFile = File(...),
    provider: str = Form(default="groq"),
):
    ext = os.path.splitext(file.filename or "audio.wav")[1].lower()
    if ext not in SUPPORTED_AUDIO:
        return JSONResponse(status_code=400, content={
            "error": f"Unsupported format. Supported: {', '.join(SUPPORTED_AUDIO)}"
        })

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="verbose_json",
            )
        transcript = result.text
        language = detect_language(transcript)
        enriched = enrich_context_with_glossary(transcript)
        confidence = abs(float(getattr(result, "avg_logprob", -0.15)))
        return {
            "transcript": transcript,
            "enriched_transcript": enriched,
            "language_detected": language,
            "confidence": round(min(confidence, 1.0), 2),
            "ready_for_agent": True,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        os.unlink(tmp_path)


@router.post("/upload")
async def analyze_file(
    file: UploadFile = File(...),
    provider: str = Form(default=None),
):
    provider = provider or settings.default_llm_provider
    ext = os.path.splitext(file.filename or "doc.txt")[1].lower()

    if ext not in SUPPORTED_DOCS:
        return JSONResponse(status_code=400, content={
            "error": f"Unsupported type. Supported: {', '.join(SUPPORTED_DOCS)}"
        })

    content = await file.read()
    extracted_text = ""

    try:
        if ext == ".txt":
            extracted_text = content.decode("utf-8", errors="ignore")

        elif ext == ".csv":
            extracted_text = content.decode("utf-8", errors="ignore")[:3000]

        elif ext == ".pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            extracted_text = "\n".join(
                p.extract_text() or "" for p in reader.pages[:5]
            )

        elif ext in {".png", ".jpg", ".jpeg"}:
            import base64
            b64 = base64.b64encode(content).decode()
            # Use openai for vision if available, else describe via text prompt
            if settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)
                msg = HumanMessage(content=[
                    {"type": "image_url", "image_url": {"url": f"data:image/{ext[1:]};base64,{b64}"}},
                    {"type": "text", "text": "Extract all visible text. Include transaction details, amounts, dates."},
                ])
                resp = llm.invoke([msg])
                extracted_text = resp.content
            else:
                extracted_text = "[Image uploaded — OpenAI key needed for vision extraction]"

        # Fraud scan via LLM
        if extracted_text and extracted_text != "[Image uploaded — OpenAI key needed for vision extraction]":
            llm = get_llm(provider=provider)
            scan_prompt = (
                f"Document (first 2000 chars):\n{extracted_text[:2000]}\n\n"
                "You are a Nigerian fintech fraud analyst. Scan for:\n"
                "1. Structuring (amounts near ₦999,999)\n"
                "2. Scam keywords (forex, investment returns, lottery, urgent)\n"
                "3. Round-trip transfers or mule patterns\n"
                "4. BVN/NIN issues\n"
                "5. CBN compliance violations\n\n"
                'Return JSON only: {"fraud_signals": [str], "summary": str, "risk_level": "low|medium|high|critical"}'
            )
            resp = get_llm(provider=provider).invoke([
                SystemMessage(content="Nigerian fintech compliance analyst. Return only valid JSON."),
                HumanMessage(content=scan_prompt),
            ])
            raw = resp.content.strip().replace("```json", "").replace("```", "").strip()
            try:
                analysis = json.loads(raw)
            except Exception:
                analysis = {"fraud_signals": [], "summary": "Parse error — try again.", "risk_level": "unknown"}
        else:
            analysis = {"fraud_signals": [], "summary": extracted_text or "No text extracted.", "risk_level": "unknown"}

        return {
            "filename": file.filename,
            "file_type": ext,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "fraud_signals_detected": analysis.get("fraud_signals", []),
            "summary": analysis.get("summary", ""),
            "risk_level": analysis.get("risk_level", "unknown"),
            "provider_used": provider,
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
