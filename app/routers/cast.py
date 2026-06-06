from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user
from app.services.cast_service import cast_service

router = APIRouter(prefix="/api/cast", tags=["cast"])


class CastPlayRequest(BaseModel):
    device_id: str
    media_id: int
    subtitle_track: int | None = None


@router.get("/devices")
def discover_devices(user: User = Depends(get_current_user)):
    devices = cast_service.discover(timeout=4.0)
    return {"devices": devices}


@router.post("/play")
def cast_play(req: CastPlayRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(MediaItem).filter(MediaItem.id == req.media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    lib = db.query(Library).filter(Library.id == item.library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=403, detail="Access denied")

    host = request.headers.get("host", request.base_url.netloc)
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    stream_url = f"{scheme}://{host}/api/stream/{item.id}?token={token}"

    from app.routers.stream import _get_content_type
    content_type = _get_content_type(item.media_type, item.file_path)

    success = cast_service.play(req.device_id, stream_url, content_type, title=item.title)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cast to device")
    return {"ok": True, "device_id": req.device_id, "media": item.title}


@router.post("/pause")
def cast_pause(device_id: str = "", user: User = Depends(get_current_user)):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    success = cast_service.pause(device_id)
    return {"ok": success}


@router.post("/stop")
def cast_stop(device_id: str = "", user: User = Depends(get_current_user)):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    success = cast_service.stop(device_id)
    return {"ok": success}


@router.get("/status")
def cast_status(device_id: str = "", user: User = Depends(get_current_user)):
    if not device_id:
        return {"state": "idle"}
    return cast_service.status(device_id)
