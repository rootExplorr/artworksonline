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
from app.models.artwork import Artwork, ArtworkImage
from app.models.review import Review
from app.schemas.artwork import ArtworkResponse, ReviewCreate, ReviewResponse

router = APIRouter(prefix="/api/artworks", tags=["artworks"])
logger = logging.getLogger(__name__)
UPLOAD_DIRECTORY = Path(__file__).resolve().parents[3] / "uploads" / "artworks"
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_IMAGES_PER_ARTWORK = 10
IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def _prepare_images(images: list[UploadFile]) -> list[tuple[str, bytes]]:
    prepared: list[tuple[str, bytes]] = []
    for image in images:
        extension = IMAGE_TYPES.get(image.content_type or "")
        if not extension:
            raise HTTPException(status_code=415, detail="Upload JPG, PNG, or WebP images.")

        contents = await image.read(MAX_IMAGE_SIZE + 1)
        if not contents:
            raise HTTPException(status_code=422, detail="Image files cannot be empty.")
        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail="Each image must be 10 MB or smaller.")
        prepared.append((extension, contents))
    return prepared


async def _save_images(images: list[tuple[str, bytes]]) -> list[Path]:
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    try:
        for extension, contents in images:
            path = UPLOAD_DIRECTORY / f"{uuid4().hex}{extension}"
            await asyncio.to_thread(path.write_bytes, contents)
            saved_paths.append(path)
    except OSError:
        _remove_image_files(saved_paths)
        raise
    return saved_paths


def _remove_image_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove uploaded image %s", path, exc_info=True)


def _artwork_image_paths(artwork: Artwork) -> set[Path]:
    paths = {UPLOAD_DIRECTORY / Path(artwork.image_url).name}
    paths.update(
        UPLOAD_DIRECTORY / Path(image.image_url).name for image in getattr(artwork, "images", [])
    )
    return paths


def _ensure_cover_image(artwork: Artwork) -> None:
    if not artwork.images:
        artwork.images.append(ArtworkImage(image_url=artwork.image_url, position=0))


@router.get("", response_model=list[ArtworkResponse])
def list_artworks(
    sort: Literal["price_asc", "price_desc"] = "price_asc",
    database: Session = Depends(get_db),
) -> list[Artwork]:
    final_price = Artwork.price * (100 - Artwork.discount_percent) / 100
    ordering = final_price.asc() if sort == "price_asc" else final_price.desc()
    statement = (
        select(Artwork)
        .options(selectinload(Artwork.reviews), selectinload(Artwork.images))
        .order_by(ordering, Artwork.id.asc())
    )
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

    image_paths = _artwork_image_paths(artwork)
    database.delete(artwork)
    database.commit()
    _remove_image_files(list(image_paths))
    return Response(status_code=204)


@router.delete(
    "/{artwork_id}/images/{image_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_admin)],
)
def delete_artwork_image(
    artwork_id: int,
    image_id: int,
    database: Session = Depends(get_db),
) -> Response:
    artwork = database.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    image = database.get(ArtworkImage, image_id)
    if image is None or image.artwork_id != artwork_id:
        raise HTTPException(status_code=404, detail="Artwork image not found.")
    if len(artwork.images) <= 1:
        raise HTTPException(status_code=409, detail="An artwork must have at least one image.")

    image_path = UPLOAD_DIRECTORY / Path(image.image_url).name
    artwork.images.remove(image)
    artwork.image_url = artwork.images[0].image_url
    database.commit()
    _remove_image_files([image_path])
    return Response(status_code=204)


@router.put("/{artwork_id}", response_model=ArtworkResponse, dependencies=[Depends(require_admin)])
async def update_artwork(
    artwork_id: int,
    title: Annotated[str, Form(max_length=120)],
    price: Annotated[Decimal, Form(gt=0)],
    discount_percent: Annotated[Decimal, Form(ge=0, le=100)] = Decimal("0"),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    images: list[UploadFile] | None = File(None),
    database: Session = Depends(get_db),
) -> Artwork:
    artwork = database.get(Artwork, artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=422, detail="Artwork title cannot be blank.")

    _ensure_cover_image(artwork)
    selected_images = images or []
    if len(artwork.images) + len(selected_images) > MAX_IMAGES_PER_ARTWORK:
        raise HTTPException(
            status_code=422,
            detail=f"An artwork can have at most {MAX_IMAGES_PER_ARTWORK} images.",
        )
    prepared_images = await _prepare_images(selected_images)
    new_image_paths = await _save_images(prepared_images)
    artwork.title = normalized_title
    artwork.description = description.strip() if description and description.strip() else None
    artwork.price = price
    artwork.discount_percent = discount_percent
    next_position = max((image.position for image in artwork.images), default=-1) + 1
    new_images = [
        ArtworkImage(
            image_url=f"/uploads/artworks/{path.name}",
            position=next_position + index,
        )
        for index, path in enumerate(new_image_paths)
    ]
    artwork.images.extend(new_images)

    try:
        database.commit()
        database.refresh(artwork)
    except Exception:
        database.rollback()
        _remove_image_files(new_image_paths)
        raise

    return artwork


@router.post("", response_model=ArtworkResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_artwork(
    title: Annotated[str, Form(max_length=120)],
    price: Annotated[Decimal, Form(gt=0)],
    discount_percent: Annotated[Decimal, Form(ge=0, le=100)] = Decimal("0"),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    images: list[UploadFile] = File(...),
    database: Session = Depends(get_db),
) -> Artwork:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=422, detail="Artwork title cannot be blank.")
    if not images:
        raise HTTPException(status_code=422, detail="Add at least one image.")
    if len(images) > MAX_IMAGES_PER_ARTWORK:
        raise HTTPException(
            status_code=422,
            detail=f"An artwork can have at most {MAX_IMAGES_PER_ARTWORK} images.",
        )

    prepared_images = await _prepare_images(images)
    image_paths = await _save_images(prepared_images)

    artwork = Artwork(
        title=normalized_title,
        description=description.strip() if description and description.strip() else None,
        price=price,
        discount_percent=discount_percent,
        image_url=f"/uploads/artworks/{image_paths[0].name}",
        images=[
            ArtworkImage(image_url=f"/uploads/artworks/{path.name}", position=index)
            for index, path in enumerate(image_paths)
        ],
    )
    try:
        database.add(artwork)
        database.commit()
        database.refresh(artwork)
    except Exception:
        database.rollback()
        _remove_image_files(image_paths)
        raise
    return artwork
