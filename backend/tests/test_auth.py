import os
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import router as auth_router
from app.api.routes.artworks import router as artworks_router
from app.database import Base, get_db
from app.models.artwork import Artwork


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "curator",
                "ADMIN_PASSWORD_HASH": PasswordHash.recommended().hash("correct horse battery staple"),
                "AUTH_SECRET_KEY": "test-secret-key-that-is-long-enough-for-authentication",
                "AUTH_COOKIE_SECURE": "false",
            },
        )
        self.environment.start()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.artwork = Artwork(
            title="Test artwork",
            description=None,
            price=Decimal("100.00"),
            discount_percent=Decimal("0"),
            image_url="/uploads/artworks/test.png",
        )
        with self.session_factory() as database:
            database.add(self.artwork)
            database.commit()
            database.refresh(self.artwork)

        self.app = FastAPI()
        self.app.include_router(auth_router)
        self.app.include_router(artworks_router)

        def override_get_db():
            database = self.session_factory()
            try:
                yield database
            finally:
                database.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.environment.stop()

    def test_public_gallery_and_reviews_work_without_admin_login(self) -> None:
        gallery = self.client.get("/api/artworks")
        review = self.client.post(
            f"/api/artworks/{self.artwork.id}/reviews",
            json={"rating": 5, "comment": "Beautiful work."},
        )

        self.assertEqual(gallery.status_code, 200)
        self.assertEqual(gallery.json()[0]["review_count"], 0)
        self.assertEqual(review.status_code, 201)

    def test_artwork_mutations_require_admin_login(self) -> None:
        responses = [
            self.client.post(
                "/api/artworks",
                data={"title": "New", "price": "10", "discount_percent": "0"},
                files={"image": ("new.png", b"image", "image/png")},
            ),
            self.client.put(
                f"/api/artworks/{self.artwork.id}",
                data={"title": "Updated", "price": "10", "discount_percent": "0"},
            ),
            self.client.delete(f"/api/artworks/{self.artwork.id}"),
        ]

        self.assertEqual([response.status_code for response in responses], [401, 401, 401])

    def test_login_sets_http_only_cookie_and_allows_admin_mutations(self) -> None:
        denied = self.client.post(
            "/api/auth/login",
            json={"username": "curator", "password": "incorrect"},
            headers={"Origin": "http://localhost:4200"},
        )
        self.assertEqual(denied.status_code, 401)

        login = self.client.post(
            "/api/auth/login",
            json={"username": "curator", "password": "correct horse battery staple"},
            headers={"Origin": "http://localhost:4200"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["authenticated"])
        self.assertIn("httponly", login.headers["set-cookie"].lower())
        self.assertEqual(self.client.get("/api/auth/session").status_code, 200)

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "test.png"
            image_path.write_bytes(b"test image")
            with patch("app.api.routes.artworks.UPLOAD_DIRECTORY", Path(directory)):
                deleted = self.client.delete(f"/api/artworks/{self.artwork.id}")

        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(image_path.exists())

        logout = self.client.post("/api/auth/logout", headers={"Origin": "http://localhost:4200"})
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/session").status_code, 401)

    def test_login_rejects_untrusted_origin(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": "curator", "password": "correct horse battery staple"},
            headers={"Origin": "https://attacker.invalid"},
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()