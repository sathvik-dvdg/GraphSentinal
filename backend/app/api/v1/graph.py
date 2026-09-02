# [WSL2]
from fastapi import APIRouter, Depends

from app.api.v1.deps import require_session_or_api_key
from app.models.schemas import GraphResponse
from app.services.graph_state import graph_state


router = APIRouter()


@router.get("/graph", response_model=GraphResponse)
async def get_graph(_: None = Depends(require_session_or_api_key)):
    return graph_state.graph_response()

