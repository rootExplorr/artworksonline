import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("Set DATABASE_URL in backend/.env before starting the API.")

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def backfill_legacy_artwork_images(database: Session) -> int:
    from app.models.artwork import Artwork, ArtworkImage

    artworks = database.scalars(select(Artwork).where(~Artwork.images.any())).all()
    for artwork in artworks:
        artwork.images.append(ArtworkImage(image_url=artwork.image_url, position=0))
    return len(artworks)
