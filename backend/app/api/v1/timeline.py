# [WSL2]
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session_or_api_key
from app.database import get_db
from app.models.schemas import TimelineResponse
from app.services.timeline_service import timeline_response


router = APIRouter()


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    last: str = "60min",
    db: Session = Depends(get_db),
    _: None = Depends(require_session_or_api_key),
):
    return timeline_response(last=last, db=db)

