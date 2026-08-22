# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_session_or_api_key
from app.services.graph_state import graph_state


router = APIRouter()


@router.get("/stats")
async def get_stats(_: None = Depends(require_session_or_api_key)):
    return graph_state.stats_response()

