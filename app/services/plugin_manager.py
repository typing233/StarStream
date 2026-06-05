import os
import json
import importlib.util
import logging
from pathlib import Path
from typing import Any

from app.config import PLUGINS_DIR
from app.services import event_bus

logger = logging.getLogger(__name__)


class PluginBase:
    name: str = "unnamed"
    version: str = "0.0.0"

    def on_load(self, context: dict):
        pass

    def on_unload(self):
        pass

    def on_event(self, event_name: str, data: dict):
        pass


class PluginManager:
    def __init__(self):
        self._plugins: dict[str, dict] = {}
        self._enabled_file = PLUGINS_DIR / ".enabled.json"

    def discover(self) -> list[dict]:
        plugins = []
        if not PLUGINS_DIR.exists():
            return plugins

        for entry in PLUGINS_DIR.iterdir():
            if not entry.is_dir():
                continue
            manifest_path = entry / "plugin.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                manifest["_dir"] = str(entry)
                manifest.setdefault("name", entry.name)
                manifest.setdefault("version", "0.0.0")
                manifest.setdefault("description", "")
                manifest.setdefault("entry_point", "main.py")
                plugins.append(manifest)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read plugin manifest at {manifest_path}: {e}")
        return plugins

    def _get_enabled_set(self) -> set:
        if self._enabled_file.exists():
            try:
                with open(self._enabled_file) as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    def _save_enabled_set(self, enabled: set):
        with open(self._enabled_file, "w") as f:
            json.dump(list(enabled), f)

    def load_plugin(self, manifest: dict) -> bool:
        name = manifest["name"]
        if name in self._plugins and self._plugins[name].get("loaded"):
            return True

        plugin_dir = manifest["_dir"]
        entry_point = os.path.join(plugin_dir, manifest["entry_point"])
        if not os.path.isfile(entry_point):
            logger.error(f"Plugin '{name}' entry point not found: {entry_point}")
            return False

        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{name}", entry_point)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, PluginBase)
                        and attr is not PluginBase):
                    plugin_class = attr
                    break

            if not plugin_class:
                logger.error(f"Plugin '{name}' has no PluginBase subclass")
                return False

            instance = plugin_class()
            instance.name = name
            instance.version = manifest.get("version", "0.0.0")
            instance.on_load({"plugin_dir": plugin_dir})

            self._plugins[name] = {
                "manifest": manifest,
                "instance": instance,
                "loaded": True,
            }

            event_bus.subscribe("*", instance.on_event)
            logger.info(f"Plugin '{name}' v{manifest['version']} loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin '{name}': {e}")
            self._plugins[name] = {"manifest": manifest, "instance": None, "loaded": False, "error": str(e)}
            return False

    def unload_plugin(self, name: str):
        if name not in self._plugins:
            return
        plugin_info = self._plugins[name]
        if plugin_info.get("instance"):
            try:
                plugin_info["instance"].on_unload()
                event_bus.unsubscribe("*", plugin_info["instance"].on_event)
            except Exception as e:
                logger.warning(f"Error unloading plugin '{name}': {e}")
        del self._plugins[name]

    def load_all(self):
        enabled = self._get_enabled_set()
        for manifest in self.discover():
            if manifest["name"] in enabled:
                self.load_plugin(manifest)

    def unload_all(self):
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)

    def enable(self, name: str) -> bool:
        enabled = self._get_enabled_set()
        enabled.add(name)
        self._save_enabled_set(enabled)

        for manifest in self.discover():
            if manifest["name"] == name:
                return self.load_plugin(manifest)
        return False

    def disable(self, name: str):
        enabled = self._get_enabled_set()
        enabled.discard(name)
        self._save_enabled_set(enabled)
        self.unload_plugin(name)

    def list_plugins(self) -> list[dict]:
        enabled = self._get_enabled_set()
        result = []
        for manifest in self.discover():
            name = manifest["name"]
            info = self._plugins.get(name, {})
            result.append({
                "name": name,
                "version": manifest.get("version", "0.0.0"),
                "description": manifest.get("description", ""),
                "enabled": name in enabled,
                "loaded": info.get("loaded", False),
                "error": info.get("error"),
            })
        return result

    def emit_event(self, event_name: str, data: dict | None = None):
        event_bus.emit(event_name, data)
        for name, info in self._plugins.items():
            if info.get("loaded") and info.get("instance"):
                try:
                    info["instance"].on_event(event_name, data or {})
                except Exception as e:
                    logger.error(f"Plugin '{name}' event handler error: {e}")


plugin_manager = PluginManager()
