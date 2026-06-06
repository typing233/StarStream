# StarStream Deployment Guide

## Requirements

- Python 3.11+
- FFmpeg (for media scanning, transcoding, cover extraction)
- SQLite (bundled with Python)

## Quick Start

```bash
cd 1-StarStream
pip install -r requirements.txt
python run.py
```

Server starts at `http://0.0.0.0:8000`. First registered user becomes admin.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STARSTREAM_SECRET` | `dev-secret-change-in-production` | JWT signing secret |
| `STARSTREAM_HOST` | `0.0.0.0` | Bind address |
| `STARSTREAM_PORT` | `8000` | Bind port |
| `STARSTREAM_BASE_URL` | `` | Base URL prefix for reverse proxy |
| `STARSTREAM_CORS_ORIGINS` | `*` | Comma-separated CORS origins |
| `STARSTREAM_LOG_LEVEL` | `INFO` | Logging level |

## Production Deployment

### Using systemd

```ini
# /etc/systemd/system/starstream.service
[Unit]
Description=StarStream Media Server
After=network.target

[Service]
Type=simple
User=starstream
WorkingDirectory=/opt/starstream
Environment=STARSTREAM_SECRET=your-secure-secret-key
Environment=STARSTREAM_HOST=127.0.0.1
Environment=STARSTREAM_PORT=8000
ExecStart=/opt/starstream/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable starstream
sudo systemctl start starstream
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name media.example.com;

    ssl_certificate /etc/letsencrypt/live/media.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/media.example.com/privkey.pem;

    client_max_body_size 10G;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

### With a URL prefix (sub-path)

Set `STARSTREAM_BASE_URL=/starstream` and update nginx:

```nginx
location /starstream/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "run.py"]
```

```bash
docker build -t starstream .
docker run -d \
  -p 8000:8000 \
  -v /path/to/media:/media:ro \
  -v starstream_data:/app/data \
  -e STARSTREAM_SECRET=your-secret \
  --name starstream \
  starstream
```

## Plugin Development

Plugins live in `app/plugins/<name>/plugin.py`. Implement the `BasePlugin` interface:

```python
from app.plugins._base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "Does something useful"

    def on_load(self, config: dict) -> None:
        self.api_key = config.get("api_key", "")

    def on_media_added(self, media_item: dict) -> None:
        # media_item has: title, media_type, file_path
        pass
```

Available hooks: `on_load`, `on_unload`, `on_media_added`, `on_media_removed`, `on_playback_started`, `on_playback_completed`, `on_library_scanned`, `on_user_registered`.

Configure plugins via the Admin panel or API:
```bash
curl -X PUT http://localhost:8000/api/plugins/my_plugin/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"config": {"api_key": "xxx"}}'
```

## Filesystem Watching

Enable auto-detection of new media files:
```bash
curl -X POST http://localhost:8000/api/libraries/1/watch \
  -H "Authorization: Bearer $TOKEN"
```

Requires the `watchdog` package. New files are automatically scanned and indexed.

## DLNA/Chromecast Casting

Cast support is automatic. The server discovers devices on the local network via SSDP (DLNA) and pychromecast. Use the Cast button in the player UI or the API:

```bash
# Discover devices
curl http://localhost:8000/api/cast/devices -H "Authorization: Bearer $TOKEN"

# Cast to a device
curl -X POST http://localhost:8000/api/cast/play \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "dlna_xxx", "media_id": 1}'
```

## Running Tests

```bash
pip install pytest httpx
python -m pytest tests/ -v
```
