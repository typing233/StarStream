import importlib
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

from app.config import PLUGINS_DIR
from app.plugins._base import BasePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self):
        self.plugins: dict[str, BasePlugin] = {}
        self._loaded = False

    def discover(self) -> list[str]:
        found = []
        if not PLUGINS_DIR.exists():
            return found
        for item in PLUGINS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("_") and (item / "plugin.py").exists():
                found.append(item.name)
        return found

    def load_all(self):
        if self._loaded:
            return
        self._loaded = True

        from app.database import SessionLocal
        from app.models import PluginRecord

        db = SessionLocal()
        try:
            discovered = self.discover()
            for name in discovered:
                record = db.query(PluginRecord).filter(PluginRecord.name == name).first()
                if not record:
                    record = PluginRecord(name=name, enabled=True)
                    db.add(record)
                    db.commit()
                    db.refresh(record)

                if record.enabled:
                    self._load_plugin(name, json.loads(record.config_json) if record.config_json else {})
        except Exception as e:
            logger.error(f"Plugin load error: {e}")
        finally:
            db.close()

    def _load_plugin(self, name: str, config: dict):
        try:
            plugin_path = PLUGINS_DIR / name / "plugin.py"
            spec = importlib.util.spec_from_file_location(f"plugins.{name}", str(plugin_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin):
                    plugin_class = attr
                    break

            if plugin_class:
                instance = plugin_class()
                instance.on_load(config)
                self.plugins[name] = instance
                logger.info(f"Loaded plugin: {name} v{instance.version}")
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")

    def unload(self, name: str):
        if name in self.plugins:
            try:
                self.plugins[name].on_unload()
            except Exception as e:
                logger.error(f"Error unloading plugin {name}: {e}")
            del self.plugins[name]

    def reload(self):
        for name in list(self.plugins.keys()):
            self.unload(name)
        self._loaded = False
        self.load_all()

    def emit(self, event: str, data: dict):
        handler_map = {
            "media_added": lambda p, d: p.on_media_added(d),
            "media_removed": lambda p, d: p.on_media_removed(d.get("media_id", 0)),
            "playback_started": lambda p, d: p.on_playback_started(d.get("user_id", 0), d.get("media_id", 0)),
            "playback_completed": lambda p, d: p.on_playback_completed(d.get("user_id", 0), d.get("media_id", 0)),
            "library_scanned": lambda p, d: p.on_library_scanned(d.get("library_id", 0), d.get("new_items", 0)),
            "user_registered": lambda p, d: p.on_user_registered(d.get("user_id", 0), d.get("username", "")),
        }
        handler = handler_map.get(event)
        if not handler:
            return
        for name, plugin in self.plugins.items():
            try:
                handler(plugin, data)
            except Exception as e:
                logger.error(f"Plugin {name} error on {event}: {e}")

    def get_status(self) -> list[dict]:
        discovered = self.discover()
        return [
            {
                "name": name,
                "loaded": name in self.plugins,
                "version": self.plugins[name].version if name in self.plugins else "unknown",
                "description": self.plugins[name].description if name in self.plugins else "",
            }
            for name in discovered
        ]


plugin_manager = PluginManager()
