import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.config import DATA_DIR
from app.database import get_db
from app.models import User, Library, MediaItem, AccessLog
from app.auth import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str
    library_count: int = 0


class RoleUpdate(BaseModel):
    role: str


class AdminLibraryResponse(BaseModel):
    id: int
    name: str
    path: str
    owner: str
    media_count: int = 0
    watch_enabled: bool = False


class SystemInfo(BaseModel):
    total_users: int
    total_libraries: int
    total_media: int
    db_size_mb: float
    data_dir_size_mb: float


@router.get("/users", response_model=List[AdminUserResponse])
def list_users(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    users = db.query(User).all()
    result = []
    for u in users:
        lib_count = db.query(Library).filter(Library.owner_id == u.id).count()
        result.append(AdminUserResponse(
            id=u.id, username=u.username, role=u.role,
            created_at=u.created_at.isoformat() if u.created_at else "",
            library_count=lib_count,
        ))
    return result


@router.put("/users/{user_id}/role")
def update_role(user_id: int, req: RoleUpdate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change own role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = req.role
    db.commit()
    return {"ok": True, "username": user.username, "role": user.role}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/libraries", response_model=List[AdminLibraryResponse])
def list_all_libraries(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    libs = db.query(Library).all()
    result = []
    for lib in libs:
        count = db.query(MediaItem).filter(MediaItem.library_id == lib.id).count()
        owner = db.query(User).filter(User.id == lib.owner_id).first()
        result.append(AdminLibraryResponse(
            id=lib.id, name=lib.name, path=lib.path,
            owner=owner.username if owner else "unknown",
            media_count=count, watch_enabled=lib.watch_enabled or False,
        ))
    return result


@router.delete("/libraries/{library_id}")
def delete_library(library_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    lib = db.query(Library).filter(Library.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    db.delete(lib)
    db.commit()
    return {"ok": True}


@router.get("/system", response_model=SystemInfo)
def system_info(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    total_users = db.query(User).count()
    total_libraries = db.query(Library).count()
    total_media = db.query(MediaItem).count()

    db_path = DATA_DIR / "starstream.db"
    db_size = os.path.getsize(db_path) / (1024 * 1024) if db_path.exists() else 0

    data_size = 0
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                data_size += os.path.getsize(fp)
            except OSError:
                pass
    data_size_mb = data_size / (1024 * 1024)

    return SystemInfo(
        total_users=total_users,
        total_libraries=total_libraries,
        total_media=total_media,
        db_size_mb=round(db_size, 2),
        data_dir_size_mb=round(data_size_mb, 2),
    )


@router.get("/logs")
def get_access_logs(
    page: int = 1, per_page: int = 50,
    db: Session = Depends(get_db), admin: User = Depends(get_admin_user),
):
    total = db.query(AccessLog).count()
    logs = (
        db.query(AccessLog)
        .order_by(AccessLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "method": log.method,
                "path": log.path,
                "status_code": log.status_code,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "ip_address": log.ip_address,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
