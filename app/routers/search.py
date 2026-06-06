from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import math

from app.database import get_db
from app.models import User, Library, MediaItem
from app.auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    id: int
    title: str
    year: int | None
    media_type: str
    artist: str | None
    album: str | None
    library_name: str
    cover_url: str


class SearchResponse(BaseModel):
    items: List[SearchResult]
    total: int
    page: int
    per_page: int
    pages: int


@router.get("", response_model=SearchResponse)
def search_media(
    q: str = Query(..., min_length=1),
    media_type: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user_lib_ids = [
        lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()
    ]
    if not user_lib_ids:
        return SearchResponse(items=[], total=0, page=1, per_page=per_page, pages=0)

    query = db.query(MediaItem).filter(MediaItem.library_id.in_(user_lib_ids))
    query = query.filter(
        MediaItem.title.ilike(f"%{q}%") | MediaItem.artist.ilike(f"%{q}%") | MediaItem.album.ilike(f"%{q}%")
    )
    if media_type:
        query = query.filter(MediaItem.media_type == media_type)

    total = query.count()
    pages = max(1, math.ceil(total / per_page)) if total > 0 else 0
    items = query.order_by(MediaItem.title).offset((page - 1) * per_page).limit(per_page).all()

    lib_names = {lib.id: lib.name for lib in db.query(Library).filter(Library.id.in_(user_lib_ids)).all()}

    return SearchResponse(
        items=[
            SearchResult(
                id=m.id, title=m.title, year=m.year, media_type=m.media_type,
                artist=m.artist, album=m.album,
                library_name=lib_names.get(m.library_id, ""),
                cover_url=f"/api/stream/{m.id}/cover",
            )
            for m in items
        ],
        total=total, page=page, per_page=per_page, pages=pages,
    )
