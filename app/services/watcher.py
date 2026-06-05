import os
import logging
import threading
from pathlib import Path
from collections import defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent, FileModifiedEvent

from app.config import settings
from app.services.scanner import ALL_EXTENSIONS, scan_media_file
from app.models import MediaItem, Library

logger = logging.getLogger(__name__)


class LibraryEventHandler(FileSystemEventHandler):
    def __init__(self, library_id: int, debounce_seconds: float = 5.0):
        super().__init__()
        self.library_id = library_id
        self.debounce_seconds = debounce_seconds
        self._pending_events: dict[str, str] = {}
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _is_media_file(self, path: str) -> bool:
        return Path(path).suffix.lower() in ALL_EXTENSIONS

    def on_created(self, event):
        if event.is_directory or not self._is_media_file(event.src_path):
            return
        self._queue_event(event.src_path, "created")

    def on_deleted(self, event):
        if event.is_directory or not self._is_media_file(event.src_path):
            return
        self._queue_event(event.src_path, "deleted")

    def on_modified(self, event):
        if event.is_directory or not self._is_media_file(event.src_path):
            return
        self._queue_event(event.src_path, "modified")

    def _queue_event(self, path: str, action: str):
        with self._lock:
            self._pending_events[path] = action
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._process_events)
            self._timer.daemon = True
            self._timer.start()

    def _process_events(self):
        with self._lock:
            events = dict(self._pending_events)
            self._pending_events.clear()

        if not events:
            return

        from app.database import SessionLocal
        db = SessionLocal()
        try:
            for path, action in events.items():
                try:
                    if action == "created":
                        existing = db.query(MediaItem).filter(MediaItem.file_path == path).first()
                        if not existing:
                            data = scan_media_file(path, self.library_id)
                            if data:
                                item = MediaItem(**data)
                                db.add(item)
                                logger.info(f"Watcher: added {path}")
                    elif action == "deleted":
                        item = db.query(MediaItem).filter(MediaItem.file_path == path).first()
                        if item:
                            db.delete(item)
                            logger.info(f"Watcher: removed {path}")
                    elif action == "modified":
                        item = db.query(MediaItem).filter(MediaItem.file_path == path).first()
                        if item:
                            data = scan_media_file(path, self.library_id)
                            if data:
                                for key, val in data.items():
                                    if key != "library_id" and key != "file_path":
                                        setattr(item, key, val)
                                logger.info(f"Watcher: updated {path}")
                except Exception as e:
                    logger.error(f"Watcher event processing error for {path}: {e}")
            db.commit()
        except Exception as e:
            logger.error(f"Watcher batch commit error: {e}")
            db.rollback()
        finally:
            db.close()


class WatcherManager:
    def __init__(self):
        self._observers: dict[int, Observer] = {}
        self._running = False

    def start(self, library_id: int, path: str):
        if library_id in self._observers:
            return
        if not os.path.isdir(path):
            logger.warning(f"Watcher: path does not exist: {path}")
            return

        handler = LibraryEventHandler(library_id, settings.watcher_debounce_seconds)
        observer = Observer()
        observer.schedule(handler, path, recursive=True)
        observer.daemon = True
        observer.start()
        self._observers[library_id] = observer
        logger.info(f"Watcher started for library {library_id}: {path}")

    def stop(self, library_id: int):
        observer = self._observers.pop(library_id, None)
        if observer:
            observer.stop()
            observer.join(timeout=5)
            logger.info(f"Watcher stopped for library {library_id}")

    def start_all(self):
        if not settings.watcher_enabled:
            logger.info("File watcher disabled by configuration")
            return

        from app.database import SessionLocal
        from app.models import Library
        db = SessionLocal()
        try:
            libraries = db.query(Library).all()
            for lib in libraries:
                self.start(lib.id, lib.path)
            self._running = True
        finally:
            db.close()

    def stop_all(self):
        for lib_id in list(self._observers.keys()):
            self.stop(lib_id)
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        return {
            "enabled": settings.watcher_enabled,
            "running": self._running,
            "watching": len(self._observers),
            "library_ids": list(self._observers.keys()),
        }


watcher_manager = WatcherManager()
