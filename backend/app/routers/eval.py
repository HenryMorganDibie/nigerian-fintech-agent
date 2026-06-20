from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.schemas import EvalRunRequest, EvalRunResponse, UploadEvalResponse, EvalSample, Transaction
from app.core.evaluation import run_evaluation, build_synthetic_dataset
from app.core.config import settings
from datetime import datetime, timezone
import csv
import io
import uuid

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


@router.post("/run", response_model=EvalRunResponse)
async def run_eval(req: EvalRunRequest):
    samples = build_synthetic_dataset() if req.use_synthetic else req.samples
    if not samples:
        raise HTTPException(400, "No samples provided. Set use_synthetic=true or supply samples[].")
    return run_evaluation(samples, provider=req.provider or settings.default_llm_provider)


@router.get("/dataset")
async def get_dataset():
    samples = build_synthetic_dataset()
    return {
        "total": len(samples),
        "fraud": sum(1 for s in samples if s.label == "fraud"),
        "legit": sum(1 for s in samples if s.label == "legit"),
        "samples": [{"id": s.transaction_id, "label": s.label} for s in samples],
    }


# ── Real-data upload ──────────────────────────────────────────────────────────
# Lets a fintech upload their own labelled transaction history (CSV) and run
# the exact same Bayesian engine against it — not just the 40 synthetic rows.

REQUIRED_COLUMNS = {"transaction_id", "label", "amount", "channel"}

CSV_TEMPLATE = (
    "transaction_id,label,amount,channel,timestamp,sender_account,recipient_account,"
    "is_new_recipient,is_new_device,is_agent_terminal,is_pos,is_post_loan_disbursement,"
    "device_changed_hours_ago,sim_replaced_hours_ago,transactions_last_hour,"
    "agent_tx_count_last_hour,bvn_verified,nin_bvn_match,narration,"
    "recent_outbound_ngn,recent_inbound_from_same_ngn\n"
    "TX001,fraud,95000,ussd,2025-05-01T03:12:00Z,0123456789,9876543210,"
    "true,false,false,false,false,,18,0,0,true,true,,0,0\n"
    "TX002,legit,12000,transfer,2025-05-01T14:20:00Z,0123456789,5551234567,"
    "false,false,false,false,false,,,0,0,true,true,school fees,0,0\n"
)


def _to_bool(v: str, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("true", "1", "yes", "y")


def _to_int(v: str, default: int = 0):
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(float(v))
    except ValueError:
        return default


def _to_float(v: str, default: float = 0.0) -> float:
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _parse_timestamp(v: str) -> datetime:
    if not v or not str(v).strip():
        return datetime.now(timezone.utc)
    raw = str(v).strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


@router.get("/upload/template")
async def download_csv_template():
    """Returns a CSV template with the exact columns expected by /eval/upload."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=naijafinai_eval_template.csv"},
    )


@router.post("/upload", response_model=UploadEvalResponse)
async def upload_and_run_eval(file: UploadFile = File(...), provider: str | None = None):
    """
    Upload a labelled CSV of real (or your own synthetic) transactions and
    score them through the same Bayesian fraud engine used everywhere else.

    Required columns: transaction_id, label (fraud|legit), amount, channel
    All other Transaction fields are optional — see /eval/upload/template.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Could not decode file as UTF-8. Please export as UTF-8 CSV.")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(400, "Empty or unreadable CSV.")

    header = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_COLUMNS - header
    if missing:
        raise HTTPException(
            400,
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Download /api/eval/upload/template for the expected format."
        )

    samples: list[EvalSample] = []
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # row 1 is header
        row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        label = row.get("label", "").lower()
        if label not in ("fraud", "legit"):
            errors.append(f"Row {i}: label must be 'fraud' or 'legit', got '{row.get('label')}'")
            continue

        try:
            tx = Transaction(
                transaction_id=row.get("transaction_id") or f"ROW{i}",
                amount=_to_float(row.get("amount"), 0.0),
                timestamp=_parse_timestamp(row.get("timestamp")),
                sender_account=row.get("sender_account") or "0000000000",
                recipient_account=row.get("recipient_account") or "0000000000",
                channel=row.get("channel") or "transfer",
                is_new_recipient=_to_bool(row.get("is_new_recipient")),
                is_new_device=_to_bool(row.get("is_new_device")),
                is_agent_terminal=_to_bool(row.get("is_agent_terminal")),
                is_pos=_to_bool(row.get("is_pos")),
                is_post_loan_disbursement=_to_bool(row.get("is_post_loan_disbursement")),
                device_changed_hours_ago=_to_int(row.get("device_changed_hours_ago"), None) if row.get("device_changed_hours_ago") else None,
                sim_replaced_hours_ago=_to_int(row.get("sim_replaced_hours_ago"), None) if row.get("sim_replaced_hours_ago") else None,
                transactions_last_hour=_to_int(row.get("transactions_last_hour"), 0),
                agent_tx_count_last_hour=_to_int(row.get("agent_tx_count_last_hour"), 0),
                bvn_verified=_to_bool(row.get("bvn_verified"), True),
                nin_bvn_match=_to_bool(row.get("nin_bvn_match"), True),
                narration=row.get("narration") or "",
                recent_outbound_ngn=_to_float(row.get("recent_outbound_ngn"), 0.0),
                recent_inbound_from_same_ngn=_to_float(row.get("recent_inbound_from_same_ngn"), 0.0),
            )
        except Exception as e:
            errors.append(f"Row {i}: {e}")
            continue

        samples.append(EvalSample(
            transaction_id=tx.transaction_id,
            label=label,
            transaction=tx,
        ))

    if not samples:
        raise HTTPException(
            400,
            "No valid rows parsed." + (f" Errors: {'; '.join(errors[:5])}" if errors else "")
        )

    result = run_evaluation(samples, provider=provider or settings.default_llm_provider)
    result_dict = result.model_dump()
    result_dict["upload_summary"] = {
        "filename": file.filename,
        "rows_parsed": len(samples),
        "rows_skipped": len(errors),
        "skip_reasons": errors[:10],
    }
    return result_dict
