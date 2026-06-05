import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user
from app.schemas import MediaResponse

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("")
def list_media(
    media_type: str | None = None,
    search: str | None = None,
    year: int | None = None,
    library_id: int | None = None,
    sort_by: str = Query("title", regex="^(title|created_at|file_size|year)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    all_library_ids = [lib.id for lib in db.query(Library).all()]
    if not all_library_ids:
        return {"items": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}

    query = db.query(MediaItem).filter(MediaItem.library_id.in_(all_library_ids))

    if media_type:
        query = query.filter(MediaItem.media_type == media_type)
    if year:
        query = query.filter(MediaItem.year == year)
    if library_id:
        if library_id not in all_library_ids:
            raise HTTPException(status_code=403, detail="Library not found")
        query = query.filter(MediaItem.library_id == library_id)
    if search:
        query = query.filter(MediaItem.title.ilike(f"%{search}%"))

    sort_column = getattr(MediaItem, sort_by, MediaItem.title)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()

    return {
        "items": [MediaResponse.model_validate(item).model_dump() for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.get("/stats")
def media_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_library_ids = [lib.id for lib in db.query(Library).all()]
    if not all_library_ids:
        return {"video": 0, "audio": 0, "image": 0, "ebook": 0, "total": 0}

    items = db.query(MediaItem).filter(MediaItem.library_id.in_(all_library_ids)).all()
    stats = {"video": 0, "audio": 0, "image": 0, "ebook": 0, "total": len(items)}
    for item in items:
        if item.media_type in stats:
            stats[item.media_type] += 1
    return stats


@router.get("/{media_id}", response_model=MediaResponse)
def get_media(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(MediaItem).filter(MediaItem.id == media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return item
