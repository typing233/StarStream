from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user
from app.config import settings
from app.services.cast_service import cast_manager

router = APIRouter(prefix="/api/v1/cast", tags=["cast"])


class CastRequest(BaseModel):
    device_id: str
    media_id: int


class ControlRequest(BaseModel):
    device_id: str
    action: str
    seek_position: float | None = None


def _accessible_library_ids(user: User, db: Session) -> list[int]:
    if user.role == "admin":
        return [lib.id for lib in db.query(Library).all()]
    return [lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()]


@router.get("/devices")
async def list_devices(user: User = Depends(get_current_user)):
    devices = await cast_manager.discover_devices()
    return {"devices": devices}


@router.post("/play")
async def cast_play(
    req: CastRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.base_url:
        raise HTTPException(
            status_code=400,
            detail="base_url not configured. Set STARSTREAM_BASE_URL for casting to work."
        )

    lib_ids = _accessible_library_ids(user, db)
    item = db.query(MediaItem).filter(
        MediaItem.id == req.media_id,
        MediaItem.library_id.in_(lib_ids),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    from app.auth import create_access_token
    cast_token = create_access_token(user.id, user.role)
    media_url = f"{settings.base_url}/api/v1/stream/file/{item.id}?token={cast_token}"

    import mimetypes
    content_type = mimetypes.guess_type(item.file_path)[0] or "video/mp4"

    success = await cast_manager.cast_to_device(req.device_id, media_url, content_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cast to device")
    return {"message": "Casting started", "device_id": req.device_id}


@router.post("/control")
async def cast_control(
    req: ControlRequest,
    user: User = Depends(get_current_user),
):
    if req.action not in ("play", "pause", "stop", "seek"):
        raise HTTPException(status_code=400, detail="Invalid action")

    kwargs = {}
    if req.action == "seek" and req.seek_position is not None:
        kwargs["position"] = req.seek_position

    success = await cast_manager.control_device(req.device_id, req.action, **kwargs)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to control device")
    return {"message": f"Action '{req.action}' sent"}


@router.get("/status/{device_id}")
async def cast_status(device_id: str, user: User = Depends(get_current_user)):
    status = await cast_manager.get_device_status(device_id)
    if not status:
        raise HTTPException(status_code=404, detail="Device not found")
    return status
