from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaResponse(BaseModel):
    id: int
    title: str
    media_type: str
    year: int | None
    duration: float | None
    cover_path: str | None
    file_size: int | None
    metadata_json: dict | None
    library_id: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[MediaResponse])
def list_media(
    media_type: str | None = None,
    search: str | None = None,
    year: int | None = None,
    library_id: int | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_library_ids = [
        lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()
    ]
    if not user_library_ids:
        return []

    query = db.query(MediaItem).filter(MediaItem.library_id.in_(user_library_ids))

    if media_type:
        query = query.filter(MediaItem.media_type == media_type)
    if year:
        query = query.filter(MediaItem.year == year)
    if library_id:
        if library_id not in user_library_ids:
            raise HTTPException(status_code=403, detail="Not your library")
        query = query.filter(MediaItem.library_id == library_id)
    if search:
        query = query.filter(MediaItem.title.ilike(f"%{search}%"))

    query = query.order_by(MediaItem.title)
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()
    return items


@router.get("/stats")
def media_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_library_ids = [
        lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()
    ]
    if not user_library_ids:
        return {"video": 0, "audio": 0, "image": 0, "ebook": 0, "total": 0}

    items = db.query(MediaItem).filter(MediaItem.library_id.in_(user_library_ids)).all()
    stats = {"video": 0, "audio": 0, "image": 0, "ebook": 0, "total": len(items)}
    for item in items:
        if item.media_type in stats:
            stats[item.media_type] += 1
    return stats


@router.get("/{media_id}", response_model=MediaResponse)
def get_media(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_library_ids = [
        lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()
    ]
    item = db.query(MediaItem).filter(
        MediaItem.id == media_id, MediaItem.library_id.in_(user_library_ids)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return item
