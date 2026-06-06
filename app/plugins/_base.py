from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    name: str = "unnamed"
    version: str = "0.1.0"
    description: str = ""

    @abstractmethod
    def on_load(self, config: dict) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def on_media_added(self, media_item: dict) -> None:
        pass

    def on_media_removed(self, media_id: int) -> None:
        pass

    def on_playback_started(self, user_id: int, media_id: int) -> None:
        pass

    def on_playback_completed(self, user_id: int, media_id: int) -> None:
        pass

    def on_library_scanned(self, library_id: int, new_items: int) -> None:
        pass

    def on_user_registered(self, user_id: int, username: str) -> None:
        pass
