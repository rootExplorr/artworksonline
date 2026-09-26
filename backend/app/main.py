from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.artworks import router as artworks_router
from app.auth import FRONTEND_ORIGINS
from app.database import Base, engine
from app.models import Artwork

UPLOAD_DIRECTORY = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ArtOnline API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(FRONTEND_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(artworks_router)
app.include_router(auth_router)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIRECTORY)), name="uploads")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
