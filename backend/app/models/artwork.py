from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Artwork(Base):
    __tablename__ = "artworks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    images: Mapped[list["ArtworkImage"]] = relationship(
        back_populates="artwork",
        cascade="all, delete-orphan",
        order_by="ArtworkImage.position, ArtworkImage.id",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="artwork", cascade="all, delete-orphan"
    )

    @property
    def review_count(self) -> int:
        return len(self.reviews)

    @property
    def average_rating(self) -> float:
        if not self.reviews:
            return 0.0
        return sum(review.rating for review in self.reviews) / len(self.reviews)

    @property
    def final_price(self) -> Decimal:
        return (self.price * (Decimal("100") - self.discount_percent) / Decimal("100")).quantize(
            Decimal("0.01")
        )


class ArtworkImage(Base):
    __tablename__ = "artwork_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    artwork_id: Mapped[int] = mapped_column(
        ForeignKey("artworks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    artwork: Mapped[Artwork] = relationship(back_populates="images")
