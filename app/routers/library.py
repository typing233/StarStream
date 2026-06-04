import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Library
from app.auth import get_current_user
from app.services.scanner import scan_library

router = APIRouter(prefix="/api/libraries", tags=["libraries"])

HOME_DIR = str(Path.home())


@router.get("/browse")
def browse_directories(
    path: str = Query(default=""),
    user: User = Depends(get_current_user),
):
    if not path:
        path = HOME_DIR

    path = os.path.realpath(path)
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    dirs = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith('.'):
                dirs.append({"name": entry.name, "path": entry.path})
    except PermissionError:
        raise HTTPException(status_code=403, detail="No permission to read this directory")

    parent = os.path.dirname(path) if path != "/" else None
    return {
        "current": path,
        "parent": parent,
        "directories": dirs,
    }


class LibraryCreate(BaseModel):
    name: str
    path: str


class LibraryResponse(BaseModel):
    id: int
    name: str
    path: str
    last_scanned: str | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[LibraryResponse])
def list_libraries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    libs = db.query(Library).filter(Library.owner_id == user.id).all()
    return [
        LibraryResponse(
            id=lib.id,
            name=lib.name,
            path=lib.path,
            last_scanned=lib.last_scanned.isoformat() if lib.last_scanned else None,
        )
        for lib in libs
    ]


@router.post("", response_model=LibraryResponse)
def create_library(
    req: LibraryCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not os.path.isdir(req.path):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    existing = db.query(Library).filter(Library.path == req.path).first()
    if existing:
        raise HTTPException(status_code=400, detail="Library path already registered")

    lib = Library(name=req.name, path=req.path, owner_id=user.id)
    db.add(lib)
    db.commit()
    db.refresh(lib)

    background_tasks.add_task(_scan_in_background, lib.id)

    return LibraryResponse(id=lib.id, name=lib.name, path=lib.path, last_scanned=None)


@router.post("/{library_id}/scan")
def rescan_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    background_tasks.add_task(_scan_in_background, lib.id)
    return {"message": "Scan started"}


@router.delete("/{library_id}")
def delete_library(
    library_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lib = db.query(Library).filter(Library.id == library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    db.delete(lib)
    db.commit()
    return {"message": "Library deleted"}


def _scan_in_background(library_id: int):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        lib = db.query(Library).filter(Library.id == library_id).first()
        if lib:
            scan_library(db, lib)
    finally:
        db.close()
