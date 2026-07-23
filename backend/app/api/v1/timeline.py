# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_api_key
from app.services.timeline_service import timeline_response


router = APIRouter()


@router.get("/timeline", dependencies=[Depends(require_api_key)])
async def get_timeline(last: str = "60min"):
    return timeline_response(last)

