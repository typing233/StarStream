import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from sqlalchemy import inspect, text

from app.database import engine, Base
from app.config import settings
from app.routers import auth, library, media, stream, admin, activity, cast, plugins

logger = logging.getLogger("starstream")


def _run_migrations():
    inspector = inspect(engine)

    if "users" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "role" not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
                conn.execute(text("UPDATE users SET role='admin' WHERE id=(SELECT MIN(id) FROM users)"))
                conn.commit()
            logger.info("Migration: added 'role' column to users table")

    Base.metadata.create_all(bind=engine)


def _setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    _run_migrations()

    from app.services.plugin_manager import plugin_manager
    from app.services.watcher import watcher_manager

    plugin_manager.load_all()
    watcher_manager.start_all()
    logger.info("StarStream started")

    yield

    watcher_manager.stop_all()
    plugin_manager.unload_all()
    logger.info("StarStream stopped")


app = FastAPI(
    title="StarStream",
    version="2.0.0",
    description="Self-hosted media streaming server with multi-user support, casting, and plugins",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "libraries", "description": "Library management"},
        {"name": "media", "description": "Media browsing and search"},
        {"name": "stream", "description": "Media streaming and transcoding"},
        {"name": "activity", "description": "Play history and activity tracking"},
        {"name": "cast", "description": "DLNA/Chromecast device casting"},
        {"name": "admin", "description": "Admin-only management endpoints"},
        {"name": "plugins", "description": "Plugin management"},
    ],
)

origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(media.router)
app.include_router(stream.router)
app.include_router(admin.router)
app.include_router(activity.router)
app.include_router(cast.router)
app.include_router(plugins.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
