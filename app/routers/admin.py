from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Library, MediaItem, ActivityLog
from app.auth import get_current_admin
from app.schemas import UserResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: str


@router.get("/users")
def list_users(user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    result = []
    for u in users:
        lib_count = db.query(Library).filter(Library.owner_id == u.id).count()
        result.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "library_count": lib_count,
        })
    return result


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    req: RoleUpdate,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot change own role")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = req.role
    db.commit()
    return {"message": f"User {target.username} role updated to {req.role}"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(Library).filter(Library.owner_id == user_id).delete()
    db.delete(target)
    db.commit()
    return {"message": f"User {target.username} deleted"}


@router.get("/stats")
def system_stats(user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_libraries = db.query(Library).count()
    total_media = db.query(MediaItem).count()
    total_size = db.query(func.sum(MediaItem.file_size)).scalar() or 0

    type_counts = {}
    for media_type in ["video", "audio", "image", "ebook"]:
        type_counts[media_type] = db.query(MediaItem).filter(MediaItem.media_type == media_type).count()

    return {
        "total_users": total_users,
        "total_libraries": total_libraries,
        "total_media": total_media,
        "total_storage_bytes": total_size,
        "media_by_type": type_counts,
    }


@router.get("/activity")
def global_activity(
    action: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    import math
    query = db.query(ActivityLog)
    if action:
        query = query.filter(ActivityLog.action == action)
    query = query.order_by(ActivityLog.created_at.desc())
    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for log in items:
        u = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None
        result.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": u.username if u else None,
            "action": log.action,
            "details_json": log.details_json,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {"items": result, "total": total, "page": page, "per_page": per_page, "total_pages": total_pages}
