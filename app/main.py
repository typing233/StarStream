from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import CORS_ORIGINS, BASE_URL
from app.database import engine, Base
from app.routers import auth, library, stream, admin, stats, cast, plugins, search
from app.services.transcoder import router as transcode_router
from app.middleware.logging_mw import AccessLoggingMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StarStream", version="2.0.0", root_path=BASE_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)
app.add_middleware(AccessLoggingMiddleware)

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(stream.router)
app.include_router(transcode_router)
app.include_router(admin.router)
app.include_router(stats.router)
app.include_router(cast.router)
app.include_router(plugins.router)
app.include_router(search.router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    return FileResponse(str(static_dir / "index.html"))


@app.on_event("startup")
def startup_event():
    from app.services.plugin_manager import plugin_manager
    plugin_manager.load_all()

    from app.services.watcher import watcher_manager
    watcher_manager.start_all()
