import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image
from mutagen import File as MutagenFile
from sqlalchemy.orm import Session

from app.config import THUMBNAILS_DIR
from app.models import MediaItem, Library

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff"}
EBOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".cbz", ".cbr"}

ALL_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS | EBOOK_EXTENSIONS

YEAR_PATTERN = re.compile(r"(?:^|[\s\.\-_\(\[])((19|20)\d{2})(?:[\s\.\-_\)\]]|$)")


def get_media_type(ext: str) -> str:
    ext = ext.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in EBOOK_EXTENSIONS:
        return "ebook"
    return "unknown"


def extract_year_from_string(text: str) -> int | None:
    matches = YEAR_PATTERN.findall(text)
    for match in reversed(matches):
        year = int(match[0])
        if 1920 <= year <= datetime.now().year + 1:
            return year
    plain = re.findall(r"((?:19|20)\d{2})", text)
    for m in reversed(plain):
        year = int(m)
        if 1920 <= year <= datetime.now().year + 1:
            return year
    return None


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
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def extract_video_thumbnail(file_path: str, output_path: str, time_offset: str = "10%") -> bool:
    try:
        probe = run_ffprobe(file_path)
        if probe and "format" in probe:
            duration = float(probe["format"].get("duration", 60))
            seek_time = duration * 0.1
        else:
            seek_time = 5

        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(seek_time), "-i", file_path,
                "-vframes", "1", "-vf", "scale=320:-1",
                "-q:v", "5", output_path,
            ],
            capture_output=True, timeout=30,
        )
        return os.path.exists(output_path)
    except subprocess.TimeoutExpired:
        return False


def extract_audio_cover(file_path: str, output_path: str) -> bool:
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return False
        if hasattr(audio, "pictures") and audio.pictures:
            with open(output_path, "wb") as f:
                f.write(audio.pictures[0].data)
            return True
        if hasattr(audio, "tags") and audio.tags:
            for key in audio.tags:
                if key.startswith("APIC") or key == "cover":
                    data = audio.tags[key]
                    pic_data = data.data if hasattr(data, "data") else bytes(data)
                    with open(output_path, "wb") as f:
                        f.write(pic_data)
                    return True
    except Exception:
        pass
    return False


def extract_image_thumbnail(file_path: str, output_path: str) -> bool:
    try:
        with Image.open(file_path) as img:
            img.thumbnail((320, 320))
            img.save(output_path, "JPEG")
        return True
    except Exception:
        return False


def scan_media_file(file_path: str, library_id: int) -> dict | None:
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in ALL_EXTENSIONS:
        return None

    media_type = get_media_type(ext)
    title = path.stem.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    year = extract_year_from_string(path.name)
    if not year:
        year = extract_year_from_string(str(path.parent.name))
    duration = None
    file_size = path.stat().st_size
    metadata = {
        "format": ext.lstrip("."),
        "file_name": path.name,
    }
    cover_path = None

    thumb_name = f"{library_id}_{hash(file_path) & 0xFFFFFFFF}.jpg"
    thumb_path = str(THUMBNAILS_DIR / thumb_name)

    if media_type == "video":
        probe = run_ffprobe(file_path)
        if probe and "format" in probe:
            duration = float(probe["format"].get("duration", 0)) or None
            metadata["format"] = probe["format"].get("format_long_name", ext.lstrip("."))
            metadata["bit_rate"] = probe["format"].get("bit_rate", "unknown")
            metadata["resolution"] = "unknown"
            metadata["codec"] = "unknown"
            audio_streams = 0
            subtitle_streams = 0
            for stream in probe.get("streams", []):
                if stream.get("codec_type") == "video" and metadata["resolution"] == "unknown":
                    w = stream.get("width", 0)
                    h = stream.get("height", 0)
                    metadata["resolution"] = f"{w}x{h}" if w and h else "unknown"
                    metadata["codec"] = stream.get("codec_name", "unknown")
                    metadata["fps"] = stream.get("r_frame_rate", "unknown")
                elif stream.get("codec_type") == "audio":
                    audio_streams += 1
                elif stream.get("codec_type") == "subtitle":
                    subtitle_streams += 1
            metadata["audio_tracks"] = audio_streams
            metadata["subtitle_tracks"] = subtitle_streams

            tags = probe["format"].get("tags", {})
            tags_lower = {k.lower(): v for k, v in tags.items()}
            if tags_lower.get("title", "").strip():
                title = tags_lower["title"].strip()
            for date_key in ("date", "creation_time", "year"):
                if date_key in tags_lower:
                    y = extract_year_from_string(tags_lower[date_key])
                    if y:
                        year = y
                        break
        if extract_video_thumbnail(file_path, thumb_path):
            cover_path = thumb_name

    elif media_type == "audio":
        try:
            audio = MutagenFile(file_path)
            if audio and audio.info:
                duration = audio.info.length
                metadata["sample_rate"] = getattr(audio.info, "sample_rate", None) or "unknown"
                metadata["channels"] = getattr(audio.info, "channels", None) or "unknown"
                metadata["bitrate"] = getattr(audio.info, "bitrate", None) or "unknown"
            else:
                metadata["sample_rate"] = "unknown"
                metadata["channels"] = "unknown"
                metadata["bitrate"] = "unknown"

            metadata["artist"] = "unknown"
            metadata["album"] = "unknown"

            if audio and audio.tags:
                tag_title = audio.tags.get("TIT2") or audio.tags.get("title") or audio.tags.get("\xa9nam")
                if tag_title:
                    title = str(tag_title[0]) if isinstance(tag_title, list) else str(tag_title)

                tag_date = (audio.tags.get("TDRC") or audio.tags.get("date")
                           or audio.tags.get("\xa9day") or audio.tags.get("TYER"))
                if tag_date:
                    date_str = str(tag_date[0] if isinstance(tag_date, list) else tag_date)
                    y = extract_year_from_string(date_str)
                    if y:
                        year = y

                tag_artist = audio.tags.get("TPE1") or audio.tags.get("artist") or audio.tags.get("\xa9ART")
                if tag_artist:
                    metadata["artist"] = str(tag_artist[0]) if isinstance(tag_artist, list) else str(tag_artist)

                tag_album = audio.tags.get("TALB") or audio.tags.get("album") or audio.tags.get("\xa9alb")
                if tag_album:
                    metadata["album"] = str(tag_album[0]) if isinstance(tag_album, list) else str(tag_album)
        except Exception:
            metadata.setdefault("sample_rate", "unknown")
            metadata.setdefault("channels", "unknown")
            metadata.setdefault("bitrate", "unknown")
            metadata.setdefault("artist", "unknown")
            metadata.setdefault("album", "unknown")

        if extract_audio_cover(file_path, thumb_path):
            cover_path = thumb_name

    elif media_type == "image":
        try:
            with Image.open(file_path) as img:
                metadata["resolution"] = f"{img.width}x{img.height}"
                metadata["mode"] = img.mode
                metadata["image_format"] = img.format or ext.lstrip(".")
        except Exception:
            metadata["resolution"] = "unknown"
            metadata["mode"] = "unknown"
            metadata["image_format"] = ext.lstrip(".")
        if extract_image_thumbnail(file_path, thumb_path):
            cover_path = thumb_name

    elif media_type == "ebook":
        metadata["format"] = ext.lstrip(".")
        metadata["pages"] = "unknown"
        if ext == ".pdf":
            try:
                result = subprocess.run(
                    ["python3", "-c",
                     f"from PIL import Image; import fitz; doc=fitz.open('{file_path}'); print(len(doc))"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip().isdigit():
                    metadata["pages"] = int(result.stdout.strip())
            except Exception:
                pass

    if not year:
        year = None

    return {
        "library_id": library_id,
        "file_path": file_path,
        "title": title,
        "media_type": media_type,
        "year": year,
        "duration": duration,
        "cover_path": cover_path,
        "file_size": file_size,
        "metadata_json": metadata,
    }


def scan_library(db: Session, library: Library) -> int:
    existing_paths = set(
        row[0] for row in db.query(MediaItem.file_path).filter(MediaItem.library_id == library.id).all()
    )

    count = 0
    current_paths = set()

    for root, dirs, files in os.walk(library.path):
        for filename in files:
            file_path = os.path.join(root, filename)
            current_paths.add(file_path)

            if file_path in existing_paths:
                continue

            ext = Path(filename).suffix.lower()
            if ext not in ALL_EXTENSIONS:
                continue

            data = scan_media_file(file_path, library.id)
            if data:
                item = MediaItem(**data)
                db.add(item)
                count += 1

    removed = existing_paths - current_paths
    if removed:
        db.query(MediaItem).filter(MediaItem.file_path.in_(removed)).delete(synchronize_session=False)

    library.last_scanned = datetime.now(timezone.utc)
    db.commit()
    return count
