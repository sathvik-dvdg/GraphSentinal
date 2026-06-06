# [WSL2]
from fastapi import APIRouter

from app.services.graph_state import graph_state


router = APIRouter()


@router.get("/stats")
async def get_stats():
    return graph_state.stats_response()

