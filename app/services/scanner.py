import os
import re
import json
import subprocess
import hashlib
from pathlib import Path

from app.config import COVERS_DIR
from app.database import SessionLocal
from app.models import Library, MediaItem

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".aac", ".m4a", ".wma", ".opus"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
EBOOK_EXTS = {".epub", ".pdf", ".mobi", ".azw3", ".cbz", ".cbr"}

YEAR_PATTERN = re.compile(r"((?:19|20)\d{2})")


def detect_media_type(ext: str) -> str | None:
    ext = ext.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in EBOOK_EXTS:
        return "ebook"
    return None


def extract_title_year(filename: str) -> tuple[str, int | None]:
    name = Path(filename).stem
    name = re.sub(r"[\._]", " ", name)
    name = re.sub(r"\[.*?\]|\(.*?\)", lambda m: m.group(), name)
    year = None
    match = YEAR_PATTERN.search(name)
    if match:
        year = int(match.group(1))
        name = name[:match.start()] + name[match.end():]
    name = re.sub(r"\(.*?\)|\[.*?\]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = Path(filename).stem
    return name, year


def run_ffprobe(file_path: str) -> dict | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None


def extract_cover_video(file_path: str, media_id: str) -> str | None:
    cover_file = COVERS_DIR / f"{media_id}.jpg"
    if cover_file.exists():
        return str(cover_file)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path, "-ss", "5",
                "-vframes", "1", "-vf", "scale=300:-1",
                "-q:v", "5", str(cover_file),
            ],
            capture_output=True, timeout=30,
        )
        if cover_file.exists() and cover_file.stat().st_size > 0:
            return str(cover_file)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def extract_cover_audio(file_path: str, media_id: str) -> str | None:
    cover_file = COVERS_DIR / f"{media_id}.jpg"
    if cover_file.exists():
        return str(cover_file)
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(file_path)
        if audio is None:
            return None
        art_data = None
        if hasattr(audio, "pictures") and audio.pictures:
            art_data = audio.pictures[0].data
        elif "APIC:" in (audio.tags or {}):
            art_data = audio.tags["APIC:"].data
        elif hasattr(audio.tags, "getall"):
            apic_list = audio.tags.getall("APIC")
            if apic_list:
                art_data = apic_list[0].data
        if art_data:
            cover_file.write_bytes(art_data)
            return str(cover_file)
    except Exception:
        pass
    return None


def extract_cover_image(file_path: str, media_id: str) -> str | None:
    cover_file = COVERS_DIR / f"{media_id}.jpg"
    if cover_file.exists():
        return str(cover_file)
    try:
        from PIL import Image
        img = Image.open(file_path)
        img.thumbnail((300, 300))
        img.convert("RGB").save(str(cover_file), "JPEG", quality=75)
        return str(cover_file)
    except Exception:
        pass
    return None


def get_audio_subtitle_tracks(probe_data: dict) -> tuple[str | None, str | None]:
    audio_tracks = []
    subtitle_tracks = []
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "audio":
            tags = stream.get("tags", {})
            audio_tracks.append({
                "index": stream["index"],
                "codec": stream.get("codec_name", "unknown"),
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
                "channels": stream.get("channels", 2),
            })
        elif stream.get("codec_type") == "subtitle":
            tags = stream.get("tags", {})
            subtitle_tracks.append({
                "index": stream["index"],
                "codec": stream.get("codec_name", "unknown"),
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
            })
    return (
        json.dumps(audio_tracks) if audio_tracks else None,
        json.dumps(subtitle_tracks) if subtitle_tracks else None,
    )


def file_hash(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()


def scan_library(library_id: int):
    db = SessionLocal()
    try:
        lib = db.query(Library).filter(Library.id == library_id).first()
        if not lib:
            return

        existing_paths = set(
            row[0] for row in db.query(MediaItem.file_path).filter(MediaItem.library_id == library_id).all()
        )

        for root, _, files in os.walk(lib.path):
            for fname in files:
                full_path = os.path.join(root, fname)
                if full_path in existing_paths:
                    continue

                ext = os.path.splitext(fname)[1].lower()
                media_type = detect_media_type(ext)
                if not media_type:
                    continue

                title, year = extract_title_year(fname)
                fsize = os.path.getsize(full_path)
                mid = file_hash(full_path)

                duration = None
                width = height = bitrate = None
                codec = None
                artist = album = None
                audio_tracks_json = None
                subtitle_tracks_json = None
                cover = None

                if media_type == "video":
                    probe = run_ffprobe(full_path)
                    if probe:
                        fmt = probe.get("format", {})
                        duration = float(fmt.get("duration", 0)) or None
                        bitrate = int(fmt.get("bit_rate", 0)) or None
                        for s in probe.get("streams", []):
                            if s.get("codec_type") == "video":
                                width = s.get("width")
                                height = s.get("height")
                                codec = s.get("codec_name")
                                break
                        audio_tracks_json, subtitle_tracks_json = get_audio_subtitle_tracks(probe)
                    cover = extract_cover_video(full_path, mid)

                elif media_type == "audio":
                    probe = run_ffprobe(full_path)
                    if probe:
                        fmt = probe.get("format", {})
                        duration = float(fmt.get("duration", 0)) or None
                        bitrate = int(fmt.get("bit_rate", 0)) or None
                        tags = fmt.get("tags", {})
                        artist = tags.get("artist") or tags.get("ARTIST")
                        album = tags.get("album") or tags.get("ALBUM")
                        if tags.get("title") or tags.get("TITLE"):
                            title = tags.get("title") or tags.get("TITLE")
                        if tags.get("date") or tags.get("DATE"):
                            date_str = tags.get("date") or tags.get("DATE")
                            ym = YEAR_PATTERN.search(date_str)
                            if ym:
                                year = int(ym.group(1))
                    cover = extract_cover_audio(full_path, mid)

                elif media_type == "image":
                    try:
                        from PIL import Image
                        img = Image.open(full_path)
                        width, height = img.size
                    except Exception:
                        pass
                    cover = extract_cover_image(full_path, mid)

                item = MediaItem(
                    library_id=library_id,
                    title=title,
                    year=year,
                    media_type=media_type,
                    file_path=full_path,
                    file_size=fsize,
                    duration=duration,
                    cover_path=cover,
                    width=width,
                    height=height,
                    bitrate=bitrate,
                    codec=codec,
                    artist=artist,
                    album=album,
                    audio_tracks=audio_tracks_json,
                    subtitle_tracks=subtitle_tracks_json,
                )
                db.add(item)

        db.commit()
    finally:
        db.close()
