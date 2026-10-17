from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, SQLModel


class Availability(StrEnum):
    AVAILABLE = "available"
    SOLD_OUT = "sold_out"
    UNKNOWN = "unknown"


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True, max_length=80)
    shop_id: str = Field(index=True, max_length=80)
    name: str = Field(max_length=160)
    description: str = Field(default="", max_length=2000)
    price_tnd: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    availability: Availability = Field(default=Availability.UNKNOWN)


class ProductInput(SQLModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    price_tnd: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    availability: Availability = Availability.UNKNOWN
