from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
PLUGINS_DIR = BASE_DIR / "plugins"

DATA_DIR.mkdir(exist_ok=True)
THUMBNAILS_DIR.mkdir(exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DIR / 'starstream.db'}"
    secret_key: str = "starstream-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    base_url: str = ""
    allowed_origins: str = "*"
    trusted_proxies: str = ""

    watcher_enabled: bool = True
    watcher_debounce_seconds: float = 5.0

    log_level: str = "INFO"

    class Config:
        env_prefix = "STARSTREAM_"


settings = Settings()
