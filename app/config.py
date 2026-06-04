from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"

DATA_DIR.mkdir(exist_ok=True)
THUMBNAILS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DIR / 'starstream.db'}"
    secret_key: str = "starstream-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    class Config:
        env_prefix = "STARSTREAM_"


settings = Settings()
