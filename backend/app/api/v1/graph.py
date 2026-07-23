# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_api_key
from app.services.graph_state import graph_state


router = APIRouter()


@router.get("/graph", dependencies=[Depends(require_api_key)])
async def get_graph():
    return graph_state.graph_response()

