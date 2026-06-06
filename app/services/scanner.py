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


def extract_cover_ebook(file_path: str, media_id: str) -> str | None:
    cover_file = COVERS_DIR / f"{media_id}.jpg"
    if cover_file.exists():
        return str(cover_file)
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".epub":
        return _extract_epub_cover(file_path, cover_file)
    if ext == ".pdf":
        return _extract_pdf_cover(file_path, cover_file)
    return None


def _extract_epub_cover(file_path: str, cover_file: Path) -> str | None:
    import zipfile
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = zf.namelist()
            cover_candidates = [n for n in names if "cover" in n.lower() and n.lower().endswith((".jpg", ".jpeg", ".png"))]
            if not cover_candidates:
                cover_candidates = [n for n in names if n.lower().endswith((".jpg", ".jpeg", ".png"))]
            if cover_candidates:
                data = zf.read(cover_candidates[0])
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(data))
                img.thumbnail((300, 400))
                img.convert("RGB").save(str(cover_file), "JPEG", quality=80)
                return str(cover_file)
    except Exception:
        pass
    return None


def _extract_pdf_cover(file_path: str, cover_file: Path) -> str | None:
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-frames:v", "1", "-vf", "scale=300:-1",
                str(cover_file),
            ],
            capture_output=True, timeout=30,
        )
        if cover_file.exists() and cover_file.stat().st_size > 0:
            return str(cover_file)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Fallback: use pdftoppm if available
    try:
        ppm_prefix = str(cover_file).replace(".jpg", "")
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "1", "-jpeg", "-scale-to", "300", file_path, ppm_prefix],
            capture_output=True, timeout=30,
        )
        ppm_file = Path(ppm_prefix + "-1.jpg")
        if ppm_file.exists():
            ppm_file.rename(cover_file)
            return str(cover_file)
    except (subprocess.TimeoutExpired, FileNotFoundError):
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


def generate_default_cover(media_id: str, title: str, media_type: str) -> str:
    cover_file = COVERS_DIR / f"{media_id}.jpg"
    if cover_file.exists():
        return str(cover_file)
    try:
        from PIL import Image, ImageDraw, ImageFont
        colors = {
            "audio": (70, 50, 120),
            "ebook": (40, 80, 60),
            "video": (80, 40, 40),
        }
        bg = colors.get(media_type, (60, 60, 80))
        img = Image.new("RGB", (300, 400), bg)
        draw = ImageDraw.Draw(img)

        icons = {"audio": "♫", "ebook": "PDF", "video": "▶"}
        icon = icons.get(media_type, "?")
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = font_large

        draw.text((150, 140), icon, fill=(255, 255, 255, 200), font=font_large, anchor="mm")

        display_title = title[:30] + "..." if len(title) > 30 else title
        lines = []
        while display_title:
            if len(display_title) <= 16:
                lines.append(display_title)
                break
            split = display_title[:16].rfind(" ")
            if split <= 0:
                split = 16
            lines.append(display_title[:split])
            display_title = display_title[split:].lstrip()

        y = 220
        for line in lines[:3]:
            draw.text((150, y), line, fill=(220, 220, 220), font=font_small, anchor="mm")
            y += 24

        img.save(str(cover_file), "JPEG", quality=80)
        return str(cover_file)
    except Exception:
        pass
    return None


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
                    if not cover:
                        cover = generate_default_cover(mid, title, "audio")

                elif media_type == "image":
                    try:
                        from PIL import Image
                        img = Image.open(full_path)
                        width, height = img.size
                    except Exception:
                        pass
                    cover = extract_cover_image(full_path, mid)

                elif media_type == "ebook":
                    cover = extract_cover_ebook(full_path, mid)
                    if not cover:
                        cover = generate_default_cover(mid, title, "ebook")

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
