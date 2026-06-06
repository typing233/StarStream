import logging
import urllib.request
import json

from app.plugins._base import BasePlugin

logger = logging.getLogger(__name__)


class MetadataScraperPlugin(BasePlugin):
    name = "example_metadata"
    version = "0.1.0"
    description = "Scrapes movie/TV metadata from OMDb API on media_added events"

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
        if not title:
            return

        try:
            url = f"http://www.omdbapi.com/?t={urllib.parse.quote(title)}&apikey={self.api_key}"
            if year:
                url += f"&y={year}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("Response") == "True":
                    logger.info(f"MetadataScraper: found metadata for '{title}': {data.get('Title')} ({data.get('Year')})")
        except Exception as e:
            logger.debug(f"MetadataScraper lookup failed for '{title}': {e}")

    def on_unload(self) -> None:
        logger.info("MetadataScraper unloaded")
