"""Helpers for a saved buyer thread. The records live in models.py."""

from shop_assistant.models import DiscussionTurn, OrderLead, OrderView


def order_view(lead: OrderLead) -> OrderView:
    """Return the saved details and the names of the ones still empty."""
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
    """Format the latest turns so the next draft can see them."""
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
