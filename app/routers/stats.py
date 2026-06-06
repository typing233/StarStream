from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
import math

from app.database import get_db
from app.models import User, Library, MediaItem, PlayEvent
from app.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


class PlayEventCreate(BaseModel):
    media_id: int
    duration_watched: float = 0
    completed: bool = False


class HistoryItem(BaseModel):
    id: int
    media_id: int
    title: str
    media_type: str
    started_at: str
    duration_watched: float
    completed: bool


class PopularItem(BaseModel):
    media_id: int
    title: str
    media_type: str
    play_count: int
    artist: str | None


class StatsSummary(BaseModel):
    total_plays: int
    total_hours_watched: float
    unique_items_played: int
    total_media_items: int


class AdminStatsOverview(BaseModel):
    total_plays: int
    total_users: int
    active_users_7d: int
    total_media: int
    total_libraries: int
    total_hours_watched: float


@router.post("/play")
def record_play(req: PlayEventCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(MediaItem).filter(MediaItem.id == req.media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    lib = db.query(Library).filter(Library.id == item.library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=403, detail="Access denied")

    event = PlayEvent(
        user_id=user.id,
        media_id=req.media_id,
        duration_watched=req.duration_watched,
        completed=req.completed,
    )
    db.add(event)
    item.play_count = (item.play_count or 0) + 1
    db.commit()

    from app.services.plugin_manager import plugin_manager
    plugin_manager.emit("playback_started", {"user_id": user.id, "media_id": req.media_id})
    if req.completed:
        plugin_manager.emit("playback_completed", {"user_id": user.id, "media_id": req.media_id})

    return {"ok": True}


@router.get("/history")
def get_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(PlayEvent, MediaItem)
        .join(MediaItem, PlayEvent.media_id == MediaItem.id)
        .filter(PlayEvent.user_id == user.id)
        .order_by(PlayEvent.started_at.desc())
    )
    total = query.count()
    pages = max(1, math.ceil(total / per_page)) if total > 0 else 0
    results = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": ev.id,
                "media_id": ev.media_id,
                "title": media.title,
                "media_type": media.media_type,
                "started_at": ev.started_at.isoformat() if ev.started_at else "",
                "duration_watched": ev.duration_watched or 0,
                "completed": ev.completed,
            }
            for ev, media in results
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/popular", response_model=List[PopularItem])
def get_popular(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user_lib_ids = [lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()]
    if not user_lib_ids:
        return []

    items = (
        db.query(MediaItem)
        .filter(MediaItem.library_id.in_(user_lib_ids), MediaItem.play_count > 0)
        .order_by(MediaItem.play_count.desc())
        .limit(20)
        .all()
    )
    return [
        PopularItem(
            media_id=m.id, title=m.title, media_type=m.media_type,
            play_count=m.play_count or 0, artist=m.artist,
        )
        for m in items
    ]


@router.get("/summary", response_model=StatsSummary)
def get_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user_lib_ids = [lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()]

    total_plays = db.query(PlayEvent).filter(PlayEvent.user_id == user.id).count()
    total_seconds = (
        db.query(func.sum(PlayEvent.duration_watched))
        .filter(PlayEvent.user_id == user.id)
        .scalar() or 0
    )
    unique_items = (
        db.query(func.count(func.distinct(PlayEvent.media_id)))
        .filter(PlayEvent.user_id == user.id)
        .scalar() or 0
    )
    total_media = db.query(MediaItem).filter(MediaItem.library_id.in_(user_lib_ids)).count() if user_lib_ids else 0

    return StatsSummary(
        total_plays=total_plays,
        total_hours_watched=round(total_seconds / 3600, 2),
        unique_items_played=unique_items,
        total_media_items=total_media,
    )


@router.get("/admin/overview", response_model=AdminStatsOverview)
def admin_overview(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    from datetime import datetime, timedelta, timezone
    total_plays = db.query(PlayEvent).count()
    total_users = db.query(User).count()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active_users = (
        db.query(func.count(func.distinct(PlayEvent.user_id)))
        .filter(PlayEvent.started_at >= week_ago)
        .scalar() or 0
    )
    total_media = db.query(MediaItem).count()
    total_libraries = db.query(Library).count()
    total_seconds = db.query(func.sum(PlayEvent.duration_watched)).scalar() or 0

    return AdminStatsOverview(
        total_plays=total_plays,
        total_users=total_users,
        active_users_7d=active_users,
        total_media=total_media,
        total_libraries=total_libraries,
        total_hours_watched=round(total_seconds / 3600, 2),
    )
