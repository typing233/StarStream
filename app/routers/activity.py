from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import get_current_user
from app.services.activity_service import record_play, get_user_history, get_user_stats

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


class PlayRecord(BaseModel):
    media_id: int
    duration_watched: float = 0
    completed: bool = False


@router.post("/play")
def log_play(
    req: PlayRecord,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record_play(db, user.id, req.media_id, req.duration_watched, req.completed)
    return {"message": "Play recorded"}


@router.get("/history")
def play_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_history(db, user.id, page, per_page)


@router.get("/stats")
def user_play_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_stats(db, user.id)
