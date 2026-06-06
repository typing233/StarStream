import os
import logging
import threading
from pathlib import Path

from app.services.scanner import detect_media_type, extract_title_year, file_hash, run_ffprobe
from app.services.scanner import extract_cover_video, extract_cover_audio, extract_cover_image
from app.services.scanner import extract_cover_ebook, generate_default_cover, get_audio_subtitle_tracks, YEAR_PATTERN

logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent, FileMovedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None


class LibraryEventHandler:
    def __init__(self, library_id: int):
        self.library_id = library_id

    if WATCHDOG_AVAILABLE:
        pass


if WATCHDOG_AVAILABLE:
    class _Handler(FileSystemEventHandler):
        def __init__(self, library_id: int):
            super().__init__()
            self.library_id = library_id
            self._lock = threading.Lock()

        def on_created(self, event):
            if event.is_directory:
                return
            self._handle_new_file(event.src_path)

        def on_deleted(self, event):
            if event.is_directory:
                return
            self._handle_removed_file(event.src_path)

        def on_moved(self, event):
            if event.is_directory:
                return
            self._handle_moved_file(event.src_path, event.dest_path)

        def _handle_new_file(self, file_path: str):
            ext = os.path.splitext(file_path)[1].lower()
            media_type = detect_media_type(ext)
            if not media_type:
                return

            with self._lock:
                from app.database import SessionLocal
                from app.models import MediaItem
                db = SessionLocal()
                try:
                    existing = db.query(MediaItem).filter(MediaItem.file_path == file_path).first()
                    if existing:
                        return

                    title, year = extract_title_year(os.path.basename(file_path))
                    fsize = os.path.getsize(file_path)
                    mid = file_hash(file_path)

                    duration = width = height = bitrate = None
                    codec = artist = album = None
                    audio_tracks_json = subtitle_tracks_json = None
                    cover = None

                    if media_type == "video":
                        probe = run_ffprobe(file_path)
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
                        cover = extract_cover_video(file_path, mid)
                    elif media_type == "audio":
                        probe = run_ffprobe(file_path)
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
                        cover = extract_cover_audio(file_path, mid)
                        if not cover:
                            cover = generate_default_cover(mid, title, "audio")
                    elif media_type == "image":
                        try:
                            from PIL import Image
                            img = Image.open(file_path)
                            width, height = img.size
                        except Exception:
                            pass
                        cover = extract_cover_image(file_path, mid)
                    elif media_type == "ebook":
                        cover = extract_cover_ebook(file_path, mid)
                        if not cover:
                            cover = generate_default_cover(mid, title, "ebook")

                    item = MediaItem(
                        library_id=self.library_id,
                        title=title, year=year, media_type=media_type,
                        file_path=file_path, file_size=fsize,
                        duration=duration, cover_path=cover,
                        width=width, height=height, bitrate=bitrate,
                        codec=codec, artist=artist, album=album,
                        audio_tracks=audio_tracks_json, subtitle_tracks=subtitle_tracks_json,
                    )
                    db.add(item)
                    db.commit()
                    logger.info(f"Watcher: added '{title}' to library {self.library_id}")

                    from app.services.plugin_manager import plugin_manager
                    plugin_manager.emit("media_added", {
                        "media_type": media_type, "title": title, "file_path": file_path,
                    })
                except Exception as e:
                    logger.error(f"Watcher error adding file: {e}")
                    db.rollback()
                finally:
                    db.close()

        def _handle_removed_file(self, file_path: str):
            from app.database import SessionLocal
            from app.models import MediaItem
            db = SessionLocal()
            try:
                item = db.query(MediaItem).filter(MediaItem.file_path == file_path).first()
                if item:
                    media_id = item.id
                    db.delete(item)
                    db.commit()
                    logger.info(f"Watcher: removed '{file_path}' from library")
                    from app.services.plugin_manager import plugin_manager
                    plugin_manager.emit("media_removed", {"media_id": media_id})
            except Exception as e:
                logger.error(f"Watcher error removing file: {e}")
                db.rollback()
            finally:
                db.close()

        def _handle_moved_file(self, src_path: str, dest_path: str):
            from app.database import SessionLocal
            from app.models import MediaItem
            db = SessionLocal()
            try:
                item = db.query(MediaItem).filter(MediaItem.file_path == src_path).first()
                if item:
                    item.file_path = dest_path
                    title, year = extract_title_year(os.path.basename(dest_path))
                    item.title = title
                    if year:
                        item.year = year
                    db.commit()
                    logger.info(f"Watcher: moved '{src_path}' -> '{dest_path}'")
            except Exception as e:
                logger.error(f"Watcher error moving file: {e}")
                db.rollback()
            finally:
                db.close()


class WatcherManager:
    def __init__(self):
        self._observers: dict[int, object] = {}

    def start_all(self):
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not installed, filesystem watching disabled")
            return

        from app.database import SessionLocal
        from app.models import Library
        db = SessionLocal()
        try:
            libs = db.query(Library).filter(Library.watch_enabled == True).all()
            for lib in libs:
                self.watch(lib.id, lib.path)
        finally:
            db.close()

    def watch(self, library_id: int, path: str):
        if not WATCHDOG_AVAILABLE:
            return
        if library_id in self._observers:
            return
        if not os.path.isdir(path):
            return

        handler = _Handler(library_id)
        observer = Observer()
        observer.schedule(handler, path, recursive=True)
        observer.daemon = True
        observer.start()
        self._observers[library_id] = observer
        logger.info(f"Watcher started for library {library_id}: {path}")

    def unwatch(self, library_id: int):
        observer = self._observers.pop(library_id, None)
        if observer:
            observer.stop()
            logger.info(f"Watcher stopped for library {library_id}")

    def is_watching(self, library_id: int) -> bool:
        return library_id in self._observers

    def stop_all(self):
        for lib_id in list(self._observers.keys()):
            self.unwatch(lib_id)


watcher_manager = WatcherManager()
