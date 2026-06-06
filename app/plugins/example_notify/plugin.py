import logging
import json
import urllib.request

from app.plugins._base import BasePlugin

logger = logging.getLogger(__name__)


class WebhookNotifyPlugin(BasePlugin):
    name = "example_notify"
    version = "0.1.0"
    description = "Sends webhook notifications for media and playback events"

    def __init__(self):
        self.webhook_url = ""
        self.events = []

    def on_load(self, config: dict) -> None:
        self.webhook_url = config.get("webhook_url", "")
        self.events = config.get("events", ["media_added", "playback_started"])
        logger.info(f"WebhookNotify loaded (url: {self.webhook_url[:30]}...)" if self.webhook_url else "WebhookNotify loaded (no URL configured)")

    def _send(self, event: str, payload: dict):
        if not self.webhook_url:
            return
        if event not in self.events:
            return
        try:
            data = json.dumps({"event": event, "data": payload}).encode()
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            logger.debug(f"WebhookNotify sent: {event}")
        except Exception as e:
            logger.warning(f"WebhookNotify failed: {e}")

    def on_media_added(self, media_item: dict) -> None:
        self._send("media_added", {"title": media_item.get("title", ""), "media_type": media_item.get("media_type", "")})

    def on_playback_started(self, user_id: int, media_id: int) -> None:
        self._send("playback_started", {"user_id": user_id, "media_id": media_id})

    def on_playback_completed(self, user_id: int, media_id: int) -> None:
        self._send("playback_completed", {"user_id": user_id, "media_id": media_id})

    def on_library_scanned(self, library_id: int, new_items: int) -> None:
        self._send("library_scanned", {"library_id": library_id, "new_items": new_items})

    def on_unload(self) -> None:
        logger.info("WebhookNotify unloaded")
