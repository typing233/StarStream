from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import PlayHistory, ActivityLog, MediaItem, User


def log_activity(db: Session, user_id: int | None, action: str, details: dict | None = None):
    log = ActivityLog(user_id=user_id, action=action, details_json=details)
    db.add(log)
    db.commit()


def record_play(db: Session, user_id: int, media_id: int, duration_watched: float, completed: bool):
    entry = PlayHistory(
        user_id=user_id,
        media_id=media_id,
        duration_watched=duration_watched,
        completed=1 if completed else 0,
    )
    db.add(entry)
    db.commit()
    log_activity(db, user_id, "media_played", {"media_id": media_id, "duration": duration_watched})


def get_user_history(db: Session, user_id: int, page: int = 1, per_page: int = 20):
    import math
    query = db.query(PlayHistory).filter(PlayHistory.user_id == user_id)
    query = query.order_by(PlayHistory.started_at.desc())
    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for h in items:
        media = db.query(MediaItem).filter(MediaItem.id == h.media_id).first()
        result.append({
            "id": h.id,
            "media_id": h.media_id,
            "media_title": media.title if media else None,
            "media_type": media.media_type if media else None,
            "cover_path": media.cover_path if media else None,
            "started_at": h.started_at.isoformat() if h.started_at else None,
            "duration_watched": h.duration_watched,
            "completed": h.completed,
        })
    return {"items": result, "total": total, "page": page, "per_page": per_page, "total_pages": total_pages}


def get_user_stats(db: Session, user_id: int):
    total_plays = db.query(PlayHistory).filter(PlayHistory.user_id == user_id).count()
    total_time = db.query(func.sum(PlayHistory.duration_watched)).filter(
        PlayHistory.user_id == user_id
    ).scalar() or 0
    completed = db.query(PlayHistory).filter(
        PlayHistory.user_id == user_id, PlayHistory.completed == 1
    ).count()
    return {
        "total_plays": total_plays,
        "total_watch_time": total_time,
        "completed_count": completed,
    }


def get_admin_dashboard(db: Session):
    from sqlalchemy import desc

    top_played = (
        db.query(MediaItem.id, MediaItem.title, MediaItem.media_type, func.count(PlayHistory.id).label("play_count"))
        .join(PlayHistory, PlayHistory.media_id == MediaItem.id)
        .group_by(MediaItem.id)
        .order_by(desc("play_count"))
        .limit(10)
        .all()
    )

    active_users = (
        db.query(User.id, User.username, func.count(PlayHistory.id).label("play_count"))
        .join(PlayHistory, PlayHistory.user_id == User.id)
        .group_by(User.id)
        .order_by(desc("play_count"))
        .limit(10)
        .all()
    )

    total_watch_time = db.query(func.sum(PlayHistory.duration_watched)).scalar() or 0

    return {
        "top_played": [{"id": r[0], "title": r[1], "media_type": r[2], "play_count": r[3]} for r in top_played],
        "active_users": [{"id": r[0], "username": r[1], "play_count": r[2]} for r in active_users],
        "total_watch_time": total_watch_time,
    }
