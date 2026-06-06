import os
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config import SECRET_KEY
from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user

router = APIRouter(prefix="/api/stream", tags=["stream"])


def get_user_flexible(request: Request, token: str = Query(default=None), db: Session = Depends(get_db)) -> User:
    tk = token or request.headers.get("authorization", "").replace("Bearer ", "")
    if not tk:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(tk, SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

CHUNK_SIZE = 1024 * 1024  # 1MB


def _verify_access(media_id: int, user: User, db: Session) -> MediaItem:
    item = db.query(MediaItem).filter(MediaItem.id == media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    lib = db.query(Library).filter(Library.id == item.library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=403, detail="Access denied")
    return item


@router.get("/{media_id}")
def stream_media(media_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_user_flexible)):
    item = _verify_access(media_id, user, db)
    if not os.path.isfile(item.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_size = os.path.getsize(item.file_path)
    range_header = request.headers.get("range")

    content_type = _get_content_type(item.media_type, item.file_path)

    if range_header:
        start, end = _parse_range(range_header, file_size)
        length = end - start + 1

        def iter_chunk():
            with open(item.file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_chunk(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    def iter_file():
        with open(item.file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@router.get("/{media_id}/cover")
def get_cover(media_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_user_flexible)):
    item = _verify_access(media_id, user, db)
    if item.cover_path and os.path.isfile(item.cover_path):
        return FileResponse(item.cover_path, media_type="image/jpeg")
    from app.services.scanner import generate_default_cover, file_hash
    mid = file_hash(item.file_path)
    cover = generate_default_cover(mid, item.title, item.media_type)
    if cover and os.path.isfile(cover):
        return FileResponse(cover, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="No cover available")


@router.get("/{media_id}/info")
def get_media_info(media_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_user_flexible)):
    item = _verify_access(media_id, user, db)
    return {
        "id": item.id,
        "title": item.title,
        "year": item.year,
        "media_type": item.media_type,
        "file_ext": os.path.splitext(item.file_path)[1].lower(),
        "duration": item.duration,
        "width": item.width,
        "height": item.height,
        "codec": item.codec,
        "bitrate": item.bitrate,
        "artist": item.artist,
        "album": item.album,
        "audio_tracks": json.loads(item.audio_tracks) if item.audio_tracks else [],
        "subtitle_tracks": json.loads(item.subtitle_tracks) if item.subtitle_tracks else [],
    }


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    range_spec = range_header.replace("bytes=", "")
    parts = range_spec.split("-")
    start = int(parts[0]) if parts[0] else 0
    end = int(parts[1]) if parts[1] else file_size - 1
    end = min(end, file_size - 1)
    return start, end


def _get_content_type(media_type: str, file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    type_map = {
        ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime", ".m4v": "video/mp4",
        ".mp3": "audio/mpeg", ".flac": "audio/flac", ".ogg": "audio/ogg",
        ".wav": "audio/wav", ".aac": "audio/aac", ".m4a": "audio/mp4",
        ".opus": "audio/opus",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".pdf": "application/pdf", ".epub": "application/epub+zip",
    }
    return type_map.get(ext, "application/octet-stream")
