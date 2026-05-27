from fastapi import APIRouter
from app.models.schemas import WorkflowRunRequest, WorkflowRunResponse
from app.core.workflows import run_workflow, SCENARIOS
from app.core.config import settings

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("/scenarios")
async def list_scenarios():
    return {"scenarios": [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in SCENARIOS.items()
    ]}


@router.post("/run")
async def run_workflow_endpoint(req: WorkflowRunRequest):
    return run_workflow(
        scenario_id=req.scenario_id,
        provider=req.provider or settings.default_llm_provider,
    )
