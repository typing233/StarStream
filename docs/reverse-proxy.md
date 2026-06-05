# StarStream 远程访问配置指南

## 环境变量配置

```bash
# 基础配置
export STARSTREAM_SERVER_HOST=0.0.0.0
export STARSTREAM_SERVER_PORT=8000

# 远程访问（投屏等功能需要）
export STARSTREAM_BASE_URL=https://stream.example.com

# CORS 配置（多个域名用逗号分隔）
export STARSTREAM_ALLOWED_ORIGINS=https://stream.example.com,http://localhost:3000

# 可信代理（设置为反向代理 IP）
export STARSTREAM_TRUSTED_PROXIES=127.0.0.1
```

## Nginx 配置

```nginx
server {
    listen 443 ssl http2;
    server_name stream.example.com;

    ssl_certificate /etc/letsencrypt/live/stream.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/stream.example.com/privkey.pem;

    client_max_body_size 0;
    proxy_buffering off;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Streaming support
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}

server {
    listen 80;
    server_name stream.example.com;
    return 301 https://$host$request_uri;
}
```

## Caddy 配置

```caddyfile
stream.example.com {
    reverse_proxy localhost:8000 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP {remote_host}

        # Disable buffering for streaming
        flush_interval -1
    }
}
```

## Docker 部署示例

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

```yaml
# docker-compose.yml
version: '3.8'
services:
  starstream:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - /media:/media:ro
    environment:
      - STARSTREAM_BASE_URL=https://stream.example.com
      - STARSTREAM_SECRET_KEY=your-secure-random-key
      - STARSTREAM_ALLOWED_ORIGINS=https://stream.example.com
    restart: unless-stopped
```

## 安全建议

1. 生产环境务必修改 `STARSTREAM_SECRET_KEY`
2. 使用 HTTPS（通过反向代理 + Let's Encrypt）
3. 配置 `STARSTREAM_ALLOWED_ORIGINS` 为你的实际域名
4. 设置防火墙，仅开放 443 端口对外
5. 定期备份 `data/starstream.db`
