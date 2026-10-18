"""Saved buyer thread and the order details collected from it."""

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class ShopConversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    shop_id: str = Field(index=True, max_length=80)


class DiscussionTurn(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(index=True)
    role: str = Field(max_length=20)
    text: str = Field(max_length=4000)


class OrderLead(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(index=True, unique=True)
    shop_id: str = Field(max_length=80)
    product_name: str = Field(default="", max_length=160)
    size: str = Field(default="", max_length=40)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=300)


class OrderView(BaseModel):
    product_name: str
    size: str
    phone: str
    address: str
    missing: list[str]


def order_view(lead: OrderLead) -> OrderView:
    values = {
        "product": lead.product_name.strip(),
        "size": lead.size.strip(),
        "phone": lead.phone.strip(),
        "address": lead.address.strip(),
    }
    return OrderView(
        product_name=lead.product_name,
        size=lead.size,
        phone=lead.phone,
        address=lead.address,
        missing=[name for name, value in values.items() if not value],
    )


def format_discussion(turns: list[DiscussionTurn]) -> str:
    if not turns:
        return ""
    lines = []
    for turn in turns[-12:]:
        speaker = "Buyer" if turn.role == "buyer" else "Assistant draft"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def remember_order(lead: OrderLead, product: str, size: str, phone: str, address: str) -> None:
    """Keep a detail that was already saved when this turn does not repeat it."""
    lead.product_name = product.strip() or lead.product_name
    lead.size = size.strip() or lead.size
    lead.phone = phone.strip() or lead.phone
    lead.address = address.strip() or lead.address
