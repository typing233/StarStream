import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, MediaItem, Library
from app.auth import get_current_user_from_token_param
from app.config import THUMBNAILS_DIR
from app.services.transcoder import (
    get_video_streams, transcode_stream, extract_subtitle, RESOLUTION_PRESETS,
)

router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/file/{media_id}")
async def stream_file(
    media_id: int,
    request: Request,
    user: User = Depends(get_current_user_from_token_param),
    db: Session = Depends(get_db),
):
    item = _get_user_media(media_id, user, db)
    file_path = item.file_path

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header:
        range_start, range_end = _parse_range(range_header, file_size)
        content_length = range_end - range_start + 1

        async def range_generator():
            with open(file_path, "rb") as f:
                f.seek(range_start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            range_generator(),
            status_code=206,
            headers={
                "Content-Range": f"bytes {range_start}-{range_end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": content_type,
            },
        )

    async def full_generator():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        full_generator(),
        headers={
            "Content-Length": str(file_size),
            "Content-Type": content_type,
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/transcode/{media_id}")
async def transcode_file(
    media_id: int,
    resolution: str = Query("720p"),
    audio_track: int = Query(0),
    start_time: float = Query(0),
    user: User = Depends(get_current_user_from_token_param),
    db: Session = Depends(get_db),
):
    item = _get_user_media(media_id, user, db)
    if item.media_type != "video":
        raise HTTPException(status_code=400, detail="Transcoding only for video")
    if resolution not in RESOLUTION_PRESETS:
        raise HTTPException(status_code=400, detail=f"Valid resolutions: {list(RESOLUTION_PRESETS.keys())}")
    if not os.path.isfile(item.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return StreamingResponse(
        transcode_stream(item.file_path, resolution, audio_track, start_time),
        media_type="video/mp2t",
        headers={"Transfer-Encoding": "chunked"},
    )


@router.get("/tracks/{media_id}")
def get_tracks(
    media_id: int,
    user: User = Depends(get_current_user_from_token_param),
    db: Session = Depends(get_db),
):
    item = _get_user_media(media_id, user, db)
    if item.media_type != "video":
        raise HTTPException(status_code=400, detail="Only video has tracks")
    return get_video_streams(item.file_path)


@router.get("/subtitle/{media_id}/{stream_index}")
def get_subtitle(
    media_id: int,
    stream_index: int,
    user: User = Depends(get_current_user_from_token_param),
    db: Session = Depends(get_db),
):
    item = _get_user_media(media_id, user, db)
    vtt_path = extract_subtitle(item.file_path, stream_index)
    if not vtt_path:
        raise HTTPException(status_code=404, detail="Could not extract subtitle")
    return FileResponse(vtt_path, media_type="text/vtt")


@router.get("/thumbnail/{filename}")
def get_thumbnail(filename: str):
    safe_name = Path(filename).name
    thumb_path = THUMBNAILS_DIR / safe_name
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(str(thumb_path), media_type="image/jpeg")


def _get_user_media(media_id: int, user: User, db: Session) -> MediaItem:
    user_library_ids = [
        lib.id for lib in db.query(Library).filter(Library.owner_id == user.id).all()
    ]
    item = db.query(MediaItem).filter(
        MediaItem.id == media_id, MediaItem.library_id.in_(user_library_ids)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    return item


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    range_str = range_header.replace("bytes=", "")
    parts = range_str.split("-")
    start = int(parts[0]) if parts[0] else 0
    end = int(parts[1]) if parts[1] else file_size - 1
    end = min(end, file_size - 1)
    return start, end
