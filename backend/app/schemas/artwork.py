from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArtworkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    price: Decimal
    discount_percent: Decimal
    final_price: Decimal
    image_url: str
    created_at: datetime
    review_count: int
    average_rating: float


class ReviewCreate(BaseModel):
    reviewer_name: str | None = Field(default=None, max_length=80)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("reviewer_name", mode="before")
    @classmethod
    def normalize_reviewer_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Review comment cannot be blank.")
        return normalized


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artwork_id: int
    reviewer_name: str | None
    rating: int
    comment: str
    created_at: datetime
