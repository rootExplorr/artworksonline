import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.artwork import Artwork
from app.models.review import Review
from app.schemas.artwork import ArtworkResponse, ReviewCreate, ReviewResponse

router = APIRouter(prefix="/api/artworks", tags=["artworks"])
logger = logging.getLogger(__name__)
UPLOAD_DIRECTORY = Path(__file__).resolve().parents[3] / "uploads" / "artworks"
MAX_IMAGE_SIZE = 10 * 1024 * 1024
IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.get("", response_model=list[ArtworkResponse])
def list_artworks(
    sort: Literal["price_asc", "price_desc"] = "price_asc",
    database: Session = Depends(get_db),
) -> list[Artwork]:
    final_price = Artwork.price * (100 - Artwork.discount_percent) / 100
    ordering = final_price.asc() if sort == "price_asc" else final_price.desc()
    statement = select(Artwork).options(selectinload(Artwork.reviews)).order_by(ordering, Artwork.id.asc())
    return list(database.scalars(statement).all())


@router.get("/{artwork_id}", response_model=ArtworkResponse)
def get_artwork(artwork_id: int, database: Session = Depends(get_db)) -> Artwork:
    artwork = database.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    return artwork


@router.get("/{artwork_id}/reviews", response_model=list[ReviewResponse])
def list_reviews(artwork_id: int, database: Session = Depends(get_db)) -> list[Review]:
    if database.get(Artwork, artwork_id) is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    statement = (
        select(Review)
        .where(Review.artwork_id == artwork_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    )
    return list(database.scalars(statement).all())


@router.post("/{artwork_id}/reviews", response_model=ReviewResponse, status_code=201)
def create_review(
    artwork_id: int,
    review_data: ReviewCreate,
    database: Session = Depends(get_db),
) -> Review:
    if database.get(Artwork, artwork_id) is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    review = Review(
        artwork_id=artwork_id,
        reviewer_name=review_data.reviewer_name,
        rating=review_data.rating,
        comment=review_data.comment,
    )
    try:
        database.add(review)
        database.commit()
        database.refresh(review)
    except Exception:
        database.rollback()
        raise
    return review


@router.delete("/{artwork_id}", status_code=204, response_class=Response, dependencies=[Depends(require_admin)])
def delete_artwork(artwork_id: int, database: Session = Depends(get_db)) -> Response:
    artwork = database.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    image_path = UPLOAD_DIRECTORY / Path(artwork.image_url).name
    database.delete(artwork)
    database.commit()
    try:
        image_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove image for deleted artwork %s", artwork_id, exc_info=True)
    return Response(status_code=204)


@router.put("/{artwork_id}", response_model=ArtworkResponse, dependencies=[Depends(require_admin)])
async def update_artwork(
    artwork_id: int,
    title: Annotated[str, Form(max_length=120)],
    price: Annotated[Decimal, Form(gt=0)],
    discount_percent: Annotated[Decimal, Form(ge=0, le=100)] = Decimal("0"),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    image: UploadFile | None = File(None),
    database: Session = Depends(get_db),
) -> Artwork:
    artwork = database.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=422, detail="Artwork title cannot be blank.")

    replacement_path: Path | None = None
    if image is not None:
        extension = IMAGE_TYPES.get(image.content_type or "")
        if not extension:
            raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

        contents = await image.read(MAX_IMAGE_SIZE + 1)
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")

        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        replacement_path = UPLOAD_DIRECTORY / f"{uuid4().hex}{extension}"
        await asyncio.to_thread(replacement_path.write_bytes, contents)

    old_image_path = UPLOAD_DIRECTORY / Path(artwork.image_url).name
    artwork.title = normalized_title
    artwork.description = description.strip() if description and description.strip() else None
    artwork.price = price
    artwork.discount_percent = discount_percent
    if replacement_path is not None:
        artwork.image_url = f"/uploads/artworks/{replacement_path.name}"

    try:
        database.commit()
        database.refresh(artwork)
    except Exception:
        database.rollback()
        if replacement_path is not None:
            replacement_path.unlink(missing_ok=True)
        raise

    if replacement_path is not None:
        try:
            old_image_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not replace image for updated artwork %s", artwork_id, exc_info=True)
    return artwork


@router.post("", response_model=ArtworkResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_artwork(
    title: Annotated[str, Form(max_length=120)],
    price: Annotated[Decimal, Form(gt=0)],
    discount_percent: Annotated[Decimal, Form(ge=0, le=100)] = Decimal("0"),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    image: UploadFile = File(...),
    database: Session = Depends(get_db),
) -> Artwork:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=422, detail="Artwork title cannot be blank.")

    extension = IMAGE_TYPES.get(image.content_type or "")
    if not extension:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

    contents = await image.read(MAX_IMAGE_SIZE + 1)
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    image_path = UPLOAD_DIRECTORY / filename
    await asyncio.to_thread(image_path.write_bytes, contents)

    artwork = Artwork(
        title=normalized_title,
        description=description.strip() if description and description.strip() else None,
        price=price,
        discount_percent=discount_percent,
        image_url=f"/uploads/artworks/{filename}",
    )
    try:
        database.add(artwork)
        database.commit()
        database.refresh(artwork)
    except Exception:
        database.rollback()
        image_path.unlink(missing_ok=True)
        raise
    return artwork
