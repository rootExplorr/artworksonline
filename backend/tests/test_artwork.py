import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes.artworks import create_review, delete_artwork, get_artwork, list_reviews, update_artwork
from app.database import Base
from app.models.artwork import Artwork
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

    def test_review_validation_rejects_invalid_ratings_and_blank_comments(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewCreate(rating=6, comment="Not valid")
        with self.assertRaises(ValidationError):
            ReviewCreate(rating=4, comment="   ")


if __name__ == "__main__":
    unittest.main()
