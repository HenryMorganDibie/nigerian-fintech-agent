"""
Voice & File Upload Router
===========================
Voice: accepts audio file, transcribes using Groq Whisper (free),
detects Nigerian language, returns transcript ready for the agent.

File: accepts PDF/image/CSV, extracts text, runs fraud signal scan.
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
    """
    Transcribe audio using Groq Whisper (free).
    Supports English, Pidgin, Yoruba, Hausa, Igbo — all Nigerian languages.
    Returns transcript + detected language.
    """
    ext = os.path.splitext(file.filename or "audio.wav")[1].lower()
    if ext not in SUPPORTED_AUDIO:
        return JSONResponse(status_code=400, content={
            "error": f"Unsupported audio format. Supported: {', '.join(SUPPORTED_AUDIO)}"
        })

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Groq Whisper is free and supports Nigerian English/Pidgin well
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language=None,  # auto-detect
                response_format="verbose_json",
            )
        transcript = transcription.text
        detected_lang = detect_language(transcript)
        enriched = enrich_context_with_glossary(transcript)
        confidence = getattr(transcription, "avg_logprob", 0.85)

        return {
            "transcript": transcript,
            "enriched_transcript": enriched,
            "language_detected": detected_lang,
            "confidence": abs(float(confidence)) if confidence else 0.85,
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
    """
    Accepts PDF, image, CSV, or text files.
    Extracts content, scans for fraud signals, returns analysis.
    """
    provider = provider or settings.default_llm_provider
    ext = os.path.splitext(file.filename or "doc.txt")[1].lower()

    if ext not in SUPPORTED_DOCS:
        return JSONResponse(status_code=400, content={
            "error": f"Unsupported file type. Supported: {', '.join(SUPPORTED_DOCS)}"
        })

    content = await file.read()
    extracted_text = ""

    try:
        if ext == ".txt":
            extracted_text = content.decode("utf-8", errors="ignore")

        elif ext == ".csv":
            extracted_text = content.decode("utf-8", errors="ignore")[:3000]

        elif ext == ".pdf":
            # pdfplumber for text extraction
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                extracted_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages[:5]
                )

        elif ext in {".png", ".jpg", ".jpeg"}:
            # Use Groq vision or fall back to description prompt
            import base64
            b64 = base64.b64encode(content).decode()
            llm = get_llm(provider="openai" if settings.openai_api_key else provider)
            from langchain_core.messages import HumanMessage
            msg = HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": f"data:image/{ext[1:]};base64,{b64}"}},
                {"type": "text", "text": "Extract all text visible in this image. Include any transaction details, amounts, account numbers (mask last 4 digits), dates."},
            ])
            resp = llm.invoke([msg])
            extracted_text = resp.content

        # Fraud signal scan using LLM
        if extracted_text:
            llm = get_llm(provider=provider)
            scan_prompt = (
                f"Document content (first 2000 chars):\n{extracted_text[:2000]}\n\n"
                "You are a Nigerian fintech fraud analyst. Scan this document for:\n"
                "1. Suspicious transaction patterns (structuring, round trips, mule accounts)\n"
                "2. Known Nigerian scam indicators (forex, investment returns, lottery)\n"
                "3. CBN compliance violations\n"
                "4. BVN/NIN issues\n\n"
                "Return JSON only: {\"fraud_signals\": [str], \"summary\": str, \"risk_level\": str}"
            )
            resp = llm.invoke([
                SystemMessage(content="You are a Nigerian fintech compliance analyst. Return only valid JSON."),
                HumanMessage(content=scan_prompt),
            ])
            raw = resp.content.strip().replace("```json", "").replace("```", "").strip()
            try:
                analysis = json.loads(raw)
            except Exception:
                analysis = {"fraud_signals": [], "summary": "Could not parse document.", "risk_level": "unknown"}
        else:
            analysis = {"fraud_signals": [], "summary": "No text extracted.", "risk_level": "unknown"}

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
