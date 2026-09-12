# [WSL2]
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import check_analyze_rate_limit, require_admin_privilege, require_session_or_api_key
from app.models.schemas import AnalyzeRequest, AnalyzeResponse, MLReloadResponse
from app.services.analysis_pipeline import analyze_flows
from app.services.inference_service import InferenceService
from app.websocket.events import emit_analysis_events


router = APIRouter()


@router.post('/analyze', response_model=AnalyzeResponse)
async def analyze_traffic(
    request: AnalyzeRequest,
    _: None = Depends(require_session_or_api_key),
    __: None = Depends(check_analyze_rate_limit),
):
    try:
        result = await asyncio.to_thread(analyze_flows, request.flows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        from app.main import sio

        await emit_analysis_events(sio, result)
    except Exception:
        pass

    return result


@router.post('/ml/reload', response_model=MLReloadResponse)
async def reload_ml_model(
    _: dict = Depends(require_admin_privilege),
):
    """R-05 (M10-F01) — Administrative endpoint to dynamically reload GraphSAGE model weights and recover from degraded mode."""
    inference = InferenceService.get_instance()
    success = inference.reload_model()
    return {
        "status": "ok" if success else "degraded",
        "mode": inference.mode,
        "degraded_reason": inference.degraded_reason or None,
        "weights_path": inference.weights_path,
    }
