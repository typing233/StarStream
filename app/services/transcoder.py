import os
import json
import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config import TRANSCODED_DIR, SUBS_DIR, SECRET_KEY
from app.database import get_db
from app.models import User, MediaItem, Library

router = APIRouter(prefix="/api/transcode", tags=["transcode"])

active_jobs: dict[str, subprocess.Popen] = {}


def _get_user(request: Request, token: str = Query(default=None), db: Session = Depends(get_db)) -> User:
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


def _verify_access(media_id: int, user: User, db: Session) -> MediaItem:
    item = db.query(MediaItem).filter(MediaItem.id == media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Media not found")
    lib = db.query(Library).filter(Library.id == item.library_id, Library.owner_id == user.id).first()
    if not lib:
        raise HTTPException(status_code=403, detail="Access denied")
    return item


@router.get("/{media_id}/hls/master.m3u8")
def hls_master(
    media_id: int,
    resolution: str = Query(default="original"),
    audio_track: int = Query(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_user),
):
    item = _verify_access(media_id, user, db)
    if item.media_type != "video":
        raise HTTPException(status_code=400, detail="Not a video")

    job_key = f"{media_id}_{resolution}_{audio_track}"
    output_dir = TRANSCODED_DIR / job_key
    output_dir.mkdir(parents=True, exist_ok=True)
    playlist_path = output_dir / "stream.m3u8"

    if not playlist_path.exists():
        _start_transcode(item.file_path, str(output_dir), resolution, audio_track)

    if not playlist_path.exists():
        import time
        for _ in range(50):
            time.sleep(0.2)
            if playlist_path.exists():
                break

    if not playlist_path.exists():
        raise HTTPException(status_code=503, detail="Transcoding in progress, retry shortly")

    return FileResponse(str(playlist_path), media_type="application/vnd.apple.mpegurl")


@router.get("/{media_id}/hls/{segment}")
def hls_segment(
    media_id: int,
    segment: str,
    resolution: str = Query(default="original"),
    audio_track: int = Query(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_user),
):
    item = _verify_access(media_id, user, db)
    job_key = f"{media_id}_{resolution}_{audio_track}"
    seg_path = TRANSCODED_DIR / job_key / segment

    if not seg_path.exists():
        import time
        for _ in range(30):
            time.sleep(0.3)
            if seg_path.exists():
                break

    if not seg_path.exists():
        raise HTTPException(status_code=404, detail="Segment not ready")

    return FileResponse(str(seg_path), media_type="video/mp2t")


@router.get("/{media_id}/subtitle/{track_index}")
def get_subtitle(
    media_id: int,
    track_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_user),
):
    item = _verify_access(media_id, user, db)
    vtt_path = SUBS_DIR / f"{media_id}_{track_index}.vtt"

    if not vtt_path.exists():
        _extract_subtitle(item.file_path, track_index, str(vtt_path))

    if not vtt_path.exists():
        raise HTTPException(status_code=404, detail="Subtitle extraction failed")

    return FileResponse(str(vtt_path), media_type="text/vtt")


def _resolution_params(resolution: str) -> list[str]:
    presets = {
        "360p": ["-vf", "scale=-2:360", "-b:v", "800k"],
        "480p": ["-vf", "scale=-2:480", "-b:v", "1500k"],
        "720p": ["-vf", "scale=-2:720", "-b:v", "3000k"],
        "1080p": ["-vf", "scale=-2:1080", "-b:v", "5000k"],
    }
    return presets.get(resolution, [])


def _start_transcode(file_path: str, output_dir: str, resolution: str, audio_track: int):
    output_playlist = os.path.join(output_dir, "stream.m3u8")
    segment_pattern = os.path.join(output_dir, "seg_%03d.ts")

    cmd = ["ffmpeg", "-y", "-i", file_path]
    cmd += ["-map", "0:v:0", "-map", f"0:a:{audio_track}"]

    res_params = _resolution_params(resolution)
    if res_params:
        cmd += res_params
    else:
        cmd += ["-c:v", "copy"]

    cmd += [
        "-c:a", "aac", "-b:a", "128k",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-hls_segment_filename", segment_pattern,
        output_playlist,
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        active_jobs[f"{output_dir}"] = proc
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffmpeg not found on system")


def _extract_subtitle(file_path: str, track_index: int, output_path: str):
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-map", f"0:s:{track_index}",
                "-c:s", "webvtt", output_path,
            ],
            capture_output=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
