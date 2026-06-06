import logging
import urllib.request
import urllib.parse
import json

from app.plugins._base import BasePlugin

logger = logging.getLogger(__name__)


class MetadataScraperPlugin(BasePlugin):
    name = "example_metadata"
    version = "0.2.0"
    description = "Scrapes movie/TV metadata from OMDb API on media_added events and writes back to DB"

    def __init__(self):
        self.api_key = ""

    def on_load(self, config: dict) -> None:
        self.api_key = config.get("omdb_api_key", "")
        logger.info(f"MetadataScraper loaded (api_key configured: {bool(self.api_key)})")

    def on_media_added(self, media_item: dict) -> None:
        if not self.api_key:
            return
        if media_item.get("media_type") != "video":
            return

        title = media_item.get("title", "")
        year = media_item.get("year")
        media_id = media_item.get("media_id")
        if not title or not media_id:
            return

        try:
            url = f"http://www.omdbapi.com/?t={urllib.parse.quote(title)}&apikey={self.api_key}"
            if year:
                url += f"&y={year}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("Response") == "True":
                    self._update_media(media_id, data)
        except Exception as e:
            logger.debug(f"MetadataScraper lookup failed for '{title}': {e}")

    def _update_media(self, media_id: int, omdb_data: dict):
        from app.database import SessionLocal
        from app.models import MediaItem

        db = SessionLocal()
        try:
            item = db.query(MediaItem).filter(MediaItem.id == media_id).first()
            if not item:
                return

            new_title = omdb_data.get("Title")
            if new_title:
                item.title = new_title

            year_str = omdb_data.get("Year", "")
            if year_str and year_str.isdigit():
                item.year = int(year_str)

            director = omdb_data.get("Director")
            if director and director != "N/A" and not item.artist:
                item.artist = director

            db.commit()
            logger.info(f"MetadataScraper: updated media {media_id} -> '{new_title}' ({year_str})")
        except Exception as e:
            logger.error(f"MetadataScraper DB update error: {e}")
            db.rollback()
        finally:
            db.close()

    def on_unload(self) -> None:
        logger.info("MetadataScraper unloaded")
