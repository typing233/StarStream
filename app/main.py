from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import engine, Base
from app.routers import auth, library, media, stream

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StarStream", version="1.0.0")

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(media.router)
app.include_router(stream.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
