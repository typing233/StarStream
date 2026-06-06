from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import engine, Base
from app.routers import auth, library, stream
from app.services.transcoder import router as transcode_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StarStream", version="1.0.0")

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(stream.router)
app.include_router(transcode_router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    return FileResponse(str(static_dir / "index.html"))
