# [WSL2]
from fastapi import APIRouter

from app.services.timeline_service import timeline_response


router = APIRouter()


@router.get("/timeline")
async def get_timeline(last: str = "60min"):
    return timeline_response(last)

