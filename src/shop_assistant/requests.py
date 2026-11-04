"""Bodies the seller sends to the API."""

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator
from sqlmodel import Field as SqlField
from sqlmodel import SQLModel

from shop_assistant.models.records import ApprovedFact, AttachmentKind, Availability


class ProductInput(SQLModel):
    """Fields the seller sends when saving a product."""

    name: str = SqlField(min_length=1, max_length=160)
    description: str = SqlField(default="", max_length=2000)
    price_tnd: Decimal | None = SqlField(default=None, ge=0, max_digits=10, decimal_places=3)
    availability: Availability = Availability.UNKNOWN
    facts: list[ApprovedFact] = Field(default_factory=list)


class InstructionInput(BaseModel):
    """The free-text note the seller just wrote."""

    text: str = Field(min_length=1, max_length=12000)


class ReplyRequest(BaseModel):
    """A test-chat message, with an optional photo, voice, video, or location."""

    message: str = Field(default="", max_length=4000)
    attachment: AttachmentKind | None = None
    conversation_id: int | None = None

    @model_validator(mode="after")
    def require_buyer_input(self) -> "ReplyRequest":
        """Reject an empty send that has no attachment either."""
        if self.attachment is None and not self.message.strip():
            raise ValueError("A buyer message or a non-text share is required")
        return self
