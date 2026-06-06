from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
import os
import math

from app.config import DATA_DIR
from app.database import get_db
from app.models import User, Library, MediaItem
from app.auth import get_current_user
from app.services.scanner import scan_library

router = APIRouter(prefix="/api/libraries", tags=["libraries"])

UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


class LibraryCreate(BaseModel):
    name: str
    path: str


class LibraryResponse(BaseModel):
    id: int
    name: str
    path: str
    media_count: int = 0
    watch_enabled: bool = False


class MediaItemResponse(BaseModel):
    id: int
    title: str
    year: int | None
    media_type: str
    file_path: str
    file_size: int
    duration: float | None
    cover_path: str | None
    artist: str | None
    album: str | None
    play_count: int = 0


class PaginatedMedia(BaseModel):
    items: List[MediaItemResponse]
    total: int
    page: int
    per_page: int
    pages: int


@router.post("", response_model=LibraryResponse)
def create_library(
    req: LibraryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not os.path.isdir(req.path):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    lib = Library(name=req.name, path=req.path, owner_id=user.id)
    db.add(lib)
    db.commit()
    db.refresh(lib)
    background_tasks.add_task(scan_library, lib.id)
    return LibraryResponse(id=lib.id, name=lib.name, path=lib.path, media_count=0)


@router.get("", response_model=List[LibraryResponse])
def list_libraries(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    libs = db.query(Library).filter(Library.owner_id == user.id).all()
    result = []
    for lib in libs:
        count = db.query(MediaItem).filter(MediaItem.library_id == lib.id).count()
        result.append(LibraryResponse(
            id=lib.id, name=lib.name, path=lib.path,
            media_count=count, watch_enabled=lib.watch_enabled or False,
        ))
    return result


@router.delete("/{library_id}")
def delete_library(library_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    db.delete(lib)
    db.commit()
    return {"ok": True}


@router.post("/{library_id}/scan")
def rescan_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    background_tasks.add_task(scan_library, lib.id)
    return {"ok": True, "message": "Scan started"}


@router.get("/{library_id}/media", response_model=PaginatedMedia)
def list_media(
    library_id: int,
    media_type: str | None = None,
    q: str | None = Query(default=None),
    sort: str = Query(default="title"),
    order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")

    query = db.query(MediaItem).filter(MediaItem.library_id == library_id)
    if media_type:
        query = query.filter(MediaItem.media_type == media_type)
    if q:
        query = query.filter(
            MediaItem.title.ilike(f"%{q}%") | MediaItem.artist.ilike(f"%{q}%") | MediaItem.album.ilike(f"%{q}%")
        )

    sort_col = {
        "title": MediaItem.title,
        "year": MediaItem.year,
        "created_at": MediaItem.created_at,
        "duration": MediaItem.duration,
        "file_size": MediaItem.file_size,
        "play_count": MediaItem.play_count,
    }.get(sort, MediaItem.title)

    if order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return PaginatedMedia(
        items=[
            MediaItemResponse(
                id=m.id, title=m.title, year=m.year, media_type=m.media_type,
                file_path=m.file_path, file_size=m.file_size, duration=m.duration,
                cover_path=m.cover_path, artist=m.artist, album=m.album,
                play_count=m.play_count or 0,
            )
            for m in items
        ],
        total=total, page=page, per_page=per_page, pages=pages,
    )


@router.post("/upload", response_model=LibraryResponse)
async def upload_library(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lib_dir = UPLOADS_DIR / f"user_{user.id}" / name.replace(" ", "_").replace("/", "_")
    lib_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        rel_path = f.filename or "unnamed"
        parts = rel_path.replace("\\", "/").split("/")
        if len(parts) > 1:
            sub_dir = lib_dir / "/".join(parts[:-1])
            sub_dir.mkdir(parents=True, exist_ok=True)
        dest = lib_dir / rel_path.replace("\\", "/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(str(dest), "wb") as out:
            content = await f.read()
            out.write(content)

    lib = Library(name=name, path=str(lib_dir), owner_id=user.id)
    db.add(lib)
    db.commit()
    db.refresh(lib)
    background_tasks.add_task(scan_library, lib.id)
    return LibraryResponse(id=lib.id, name=lib.name, path=lib.path, media_count=0)


@router.post("/{library_id}/watch")
def enable_watch(library_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    lib.watch_enabled = True
    db.commit()
    from app.services.watcher import watcher_manager
    watcher_manager.watch(lib.id, lib.path)
    return {"ok": True, "message": f"Watching {lib.name}"}


@router.delete("/{library_id}/watch")
def disable_watch(library_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    lib.watch_enabled = False
    db.commit()
    from app.services.watcher import watcher_manager
    watcher_manager.unwatch(lib.id)
    return {"ok": True, "message": f"Stopped watching {lib.name}"}


@router.get("/watch/status")
def watch_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.watcher import watcher_manager
    libs = db.query(Library).filter(Library.owner_id == user.id, Library.watch_enabled == True).all()
    return [
        {"library_id": lib.id, "name": lib.name, "active": watcher_manager.is_watching(lib.id)}
        for lib in libs
    ]
