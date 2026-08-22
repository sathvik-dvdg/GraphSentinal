# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_session_or_api_key
from app.services.timeline_service import timeline_response


router = APIRouter()


@router.get("/timeline")
async def get_timeline(last: str = "60min", _: None = Depends(require_session_or_api_key)):
    return timeline_response(last)

