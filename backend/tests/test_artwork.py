import unittest
from io import BytesIO
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.api.routes.artworks import (
    create_artwork,
    create_review,
    delete_artwork,
    delete_artwork_image,
    get_artwork,
    list_reviews,
    update_artwork,
)
from app.database import Base, backfill_legacy_artwork_images
from app.models.artwork import Artwork, ArtworkImage
from app.models.review import Review
from app.schemas.artwork import ArtworkResponse, ReviewCreate


class ArtworkPriceTests(unittest.TestCase):
    def test_final_price_applies_percentage_discount(self) -> None:
        artwork = Artwork(price=Decimal("125.00"), discount_percent=Decimal("20"))

        self.assertEqual(artwork.final_price, Decimal("100.00"))

    def test_full_discount_results_in_zero(self) -> None:
        artwork = Artwork(price=Decimal("125.00"), discount_percent=Decimal("100"))

        self.assertEqual(artwork.final_price, Decimal("0.00"))


class ArtworkDeletionTests(unittest.TestCase):
    def test_delete_removes_record_and_uploaded_image(self) -> None:
        artwork = SimpleNamespace(image_url="/uploads/artworks/example.jpg")
        database = Mock()
        database.get.return_value = artwork

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "example.jpg"
            image_path.write_bytes(b"image")
            with patch("app.api.routes.artworks.UPLOAD_DIRECTORY", Path(directory)):
                response = delete_artwork(17, database)

        self.assertEqual(response.status_code, 204)
        database.delete.assert_called_once_with(artwork)
        database.commit.assert_called_once_with()
        self.assertFalse(image_path.exists())

    def test_delete_returns_not_found_for_missing_artwork(self) -> None:
        database = Mock()
        database.get.return_value = None

        with self.assertRaises(HTTPException) as error:
            delete_artwork(17, database)

        self.assertEqual(error.exception.status_code, 404)
        database.delete.assert_not_called()
        database.commit.assert_not_called()


class ArtworkUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_changes_artwork_fields_without_replacing_image(self) -> None:
        artwork = SimpleNamespace(
            image_url="/uploads/artworks/example.jpg",
            title="Original",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            images=[],
        )
        database = Mock()
        database.get.return_value = artwork

        result = await update_artwork(
            17,
            "Updated title",
            Decimal("150.00"),
            Decimal("10"),
            "Updated description",
            None,
            database,
        )

        self.assertIs(result, artwork)
        self.assertEqual(artwork.title, "Updated title")
        self.assertEqual(artwork.description, "Updated description")
        self.assertEqual(artwork.price, Decimal("150.00"))
        self.assertEqual(artwork.discount_percent, Decimal("10"))
        self.assertEqual(artwork.image_url, "/uploads/artworks/example.jpg")
        database.commit.assert_called_once_with()
        database.refresh.assert_called_once_with(artwork)

    def test_get_artwork_returns_not_found_for_missing_record(self) -> None:
        database = Mock()
        database.get.return_value = None

        with self.assertRaises(HTTPException) as error:
            get_artwork(17, database)

        self.assertEqual(error.exception.status_code, 404)


def create_image_upload(filename: str, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(b"image data"),
        headers=Headers({"content-type": content_type}),
    )


class ArtworkImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.database = Session(self.engine)
        self.temp_directory = TemporaryDirectory()
        self.upload_directory = Path(self.temp_directory.name) / "artworks"
        self.upload_patch = patch("app.api.routes.artworks.UPLOAD_DIRECTORY", self.upload_directory)
        self.upload_patch.start()

    def tearDown(self) -> None:
        self.database.close()
        self.engine.dispose()
        self.upload_patch.stop()
        self.temp_directory.cleanup()

    async def test_create_artwork_stores_multiple_ordered_images(self) -> None:
        artwork = await create_artwork(
            title="A small collection",
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            description=None,
            images=[create_image_upload("cover.jpg"), create_image_upload("detail.png", "image/png")],
            database=self.database,
        )

        self.assertEqual(len(artwork.images), 2)
        self.assertEqual([image.position for image in artwork.images], [0, 1])
        self.assertEqual(artwork.image_url, artwork.images[0].image_url)
        self.assertEqual(len(list(self.upload_directory.iterdir())), 2)
        response = ArtworkResponse.model_validate(artwork)
        self.assertEqual([image.position for image in response.images], [0, 1])

    async def test_update_adds_images_without_replacing_cover(self) -> None:
        artwork = Artwork(
            title="Existing work",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url="/uploads/artworks/cover.jpg",
            images=[ArtworkImage(image_url="/uploads/artworks/cover.jpg", position=0)],
        )
        self.database.add(artwork)
        self.database.commit()
        cover_url = artwork.image_url

        updated = await update_artwork(
            artwork_id=artwork.id,
            title="Updated work",
            price=Decimal("120.00"),
            discount_percent=Decimal("0"),
            description=None,
            images=[create_image_upload("additional.webp", "image/webp")],
            database=self.database,
        )

        self.assertEqual(len(updated.images), 2)
        self.assertEqual(updated.image_url, cover_url)
        self.assertEqual(updated.images[1].position, 1)

    async def test_create_rejects_more_than_ten_images(self) -> None:
        with self.assertRaises(HTTPException) as error:
            await create_artwork(
                title="Too many",
                price=Decimal("100.00"),
                discount_percent=Decimal("0"),
                description=None,
                images=[create_image_upload(f"{index}.jpg") for index in range(11)],
                database=self.database,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(list(self.upload_directory.glob("*")) if self.upload_directory.exists() else [], [])

    async def test_update_rejects_more_than_ten_total_images(self) -> None:
        artwork = Artwork(
            title="Full gallery",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url="/uploads/artworks/0.jpg",
            images=[
                ArtworkImage(image_url=f"/uploads/artworks/{index}.jpg", position=index)
                for index in range(10)
            ],
        )
        self.database.add(artwork)
        self.database.commit()

        with self.assertRaises(HTTPException) as error:
            await update_artwork(
                artwork_id=artwork.id,
                title="Full gallery",
                price=Decimal("100.00"),
                discount_percent=Decimal("0"),
                description=None,
                images=[create_image_upload("extra.jpg")],
                database=self.database,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.assertFalse(self.upload_directory.exists())

    def test_removing_cover_promotes_next_image(self) -> None:
        cover = ArtworkImage(image_url="/uploads/artworks/cover.jpg", position=0)
        secondary = ArtworkImage(image_url="/uploads/artworks/second.jpg", position=1)
        artwork = Artwork(
            title="Two images",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url=cover.image_url,
            images=[cover, secondary],
        )
        self.database.add(artwork)
        self.database.commit()
        self.upload_directory.mkdir(parents=True)
        (self.upload_directory / "cover.jpg").write_bytes(b"cover")

        response = delete_artwork_image(artwork.id, cover.id, self.database)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(artwork.image_url, secondary.image_url)
        self.assertEqual([image.id for image in artwork.images], [secondary.id])
        self.assertFalse((self.upload_directory / "cover.jpg").exists())

    def test_last_image_cannot_be_removed(self) -> None:
        image = ArtworkImage(image_url="/uploads/artworks/only.jpg", position=0)
        artwork = Artwork(
            title="One image",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url=image.image_url,
            images=[image],
        )
        self.database.add(artwork)
        self.database.commit()

        with self.assertRaises(HTTPException) as error:
            delete_artwork_image(artwork.id, image.id, self.database)

        self.assertEqual(error.exception.status_code, 409)

    def test_backfill_adds_existing_cover_to_image_gallery(self) -> None:
        artwork = Artwork(
            title="Legacy artwork",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url="/uploads/artworks/legacy.jpg",
        )
        self.database.add(artwork)
        self.database.commit()

        migrated = backfill_legacy_artwork_images(self.database)
        self.database.commit()
        self.database.refresh(artwork)

        self.assertEqual(migrated, 1)
        self.assertEqual(len(artwork.images), 1)
        self.assertEqual(artwork.images[0].image_url, artwork.image_url)


class ArtworkReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.database = Session(self.engine)
        self.artwork = Artwork(
            title="Test artwork",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url="/uploads/artworks/test.jpg",
        )
        self.database.add(self.artwork)
        self.database.commit()

    def tearDown(self) -> None:
        self.database.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_review_is_persisted_and_included_in_artwork_rating_summary(self) -> None:
        review_data = ReviewCreate(reviewer_name="  Alex  ", rating=5, comment="  Beautiful work.  ")

        created = create_review(self.artwork.id, review_data, self.database)
        persisted_reviews = list_reviews(self.artwork.id, self.database)
        persisted = self.database.scalar(select(Review).where(Review.id == created.id))
        self.database.refresh(self.artwork)

        self.assertIsNotNone(persisted)
        self.assertEqual(persisted_reviews, [created])
        self.assertEqual(persisted.reviewer_name, "Alex")
        self.assertEqual(persisted.comment, "Beautiful work.")
        self.assertEqual(self.artwork.review_count, 1)
        self.assertEqual(self.artwork.average_rating, 5)
        artwork_response = ArtworkResponse.model_validate(self.artwork)
        self.assertEqual(artwork_response.review_count, 1)
        self.assertEqual(artwork_response.average_rating, 5)

    def test_artwork_without_reviews_has_zero_summary(self) -> None:
        artwork_response = ArtworkResponse.model_validate(self.artwork)

        self.assertEqual(artwork_response.review_count, 0)
        self.assertEqual(artwork_response.average_rating, 0)
        self.assertEqual(artwork_response.images, [])

    def test_review_validation_rejects_invalid_ratings_and_blank_comments(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewCreate(rating=6, comment="Not valid")
        with self.assertRaises(ValidationError):
            ReviewCreate(rating=4, comment="   ")


if __name__ == "__main__":
    unittest.main()
