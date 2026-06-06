import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
COVERS_DIR = DATA_DIR / "covers"
SUBS_DIR = DATA_DIR / "subs"
TRANSCODED_DIR = DATA_DIR / "transcoded"

DATA_DIR.mkdir(exist_ok=True)
COVERS_DIR.mkdir(exist_ok=True)
SUBS_DIR.mkdir(exist_ok=True)
TRANSCODED_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'starstream.db'}"
SECRET_KEY = os.environ.get("STARSTREAM_SECRET", "dev-secret-change-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
