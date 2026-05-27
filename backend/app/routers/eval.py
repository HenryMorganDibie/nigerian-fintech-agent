from fastapi import APIRouter
from app.models.schemas import EvalRunRequest, EvalRunResponse
from app.core.evaluation import run_evaluation, build_synthetic_dataset
from app.core.config import settings

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


@router.post("/run", response_model=EvalRunResponse)
async def run_eval(req: EvalRunRequest):
    samples = build_synthetic_dataset() if req.use_synthetic else req.samples
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
