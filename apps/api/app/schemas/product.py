import uuid
from datetime import datetime

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    gender: str = "mixte"


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    gender: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    category_id: uuid.UUID
    barcode: str | None = None
    size: str | None = None
    color: str | None = None
    brand: str | None = None
    purchase_price: float = 0
    sale_price: float = 0
    status: str = "stock"
    week_number: int | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: uuid.UUID | None = None
    size: str | None = None
    color: str | None = None
    brand: str | None = None
    photo_url: str | None = None
    purchase_price: float | None = None
    sale_price: float | None = None
    status: str | None = None
    week_number: int | None = None
    zone_id: uuid.UUID | None = None
    shelf_date: datetime | None = None
    description: str | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    barcode: str
    name: str
    category_id: uuid.UUID
    size: str | None
    color: str | None
    brand: str | None
    photo_url: str | None
    purchase_price: float
    sale_price: float
    status: str
    week_number: int | None
    trend_score: float | None
    shelf_date: datetime | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceGridResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    min_purchase: float
    max_purchase: float
    sale_price: float

    model_config = {"from_attributes": True}
