from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import os
import shutil

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
        result.append(LibraryResponse(id=lib.id, name=lib.name, path=lib.path, media_count=count))
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


@router.get("/{library_id}/media", response_model=List[MediaItemResponse])
def list_media(
    library_id: int,
    media_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    q = db.query(MediaItem).filter(MediaItem.library_id == library_id)
    if media_type:
        q = q.filter(MediaItem.media_type == media_type)
    return [
        MediaItemResponse(
            id=m.id, title=m.title, year=m.year, media_type=m.media_type,
            file_path=m.file_path, file_size=m.file_size, duration=m.duration,
            cover_path=m.cover_path, artist=m.artist, album=m.album,
        )
        for m in q.all()
    ]


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
