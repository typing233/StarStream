#!/usr/bin/env python3
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips=settings.trusted_proxies if settings.trusted_proxies else None,
    )
