# [WSL2]
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import check_analyze_rate_limit, require_api_key
from app.models.schemas import AnalyzeRequest
from app.services.analysis_pipeline import analyze_flows
from app.websocket.events import emit_analysis_events


router = APIRouter()


@router.post('/analyze')
async def analyze_traffic(
    request: AnalyzeRequest,
    _: None = Depends(require_api_key),
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
