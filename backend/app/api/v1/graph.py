# [WSL2]
from fastapi import APIRouter

from app.services.graph_state import graph_state


router = APIRouter()


@router.get("/graph")
async def get_graph():
    return graph_state.graph_response()

