# StarStream Plugin System

## Creating a Plugin

1. Create a directory under `plugins/` with your plugin name
2. Add a `plugin.json` manifest file
3. Create your entry point Python file

## Manifest Format (plugin.json)

```json
{
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "What this plugin does",
    "author": "Your Name",
    "entry_point": "main.py"
}
```

## Plugin Entry Point

Your entry point file must contain a class that inherits from `PluginBase`:

```python
from app.services.plugin_manager import PluginBase

class MyPlugin(PluginBase):
    def on_load(self, context: dict):
        """Called when plugin is loaded. context contains plugin_dir path."""
        print(f"Plugin loaded from {context['plugin_dir']}")

    def on_unload(self):
        """Called when plugin is disabled or server shuts down."""
        pass

    def on_event(self, event_name: str, data: dict):
        """Called for each system event."""
        if event_name == "media_added":
            print(f"New media: {data.get('title')}")
```

## Available Events

| Event | Data | Description |
|-------|------|-------------|
| `media_added` | `{media_id, title, media_type, file_path}` | New media file scanned |
| `media_removed` | `{media_id, file_path}` | Media file removed |
| `media_played` | `{user_id, media_id, duration}` | User played media |
| `scan_complete` | `{library_id, items_added, items_removed}` | Library scan finished |
| `user_login` | `{user_id, username}` | User logged in |

## Management

Plugins are managed via the admin panel or API:
- `GET /api/v1/admin/plugins` - List all plugins
- `POST /api/v1/admin/plugins/{name}/enable` - Enable a plugin
- `POST /api/v1/admin/plugins/{name}/disable` - Disable a plugin
