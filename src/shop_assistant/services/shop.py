"""Saved threads, product views, and token totals."""

import os
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from shop_assistant.db import DEMO_SHOP_ID
from shop_assistant.models import (
    ApprovedFact,
    DiscussionTurn,
    InstructionView,
    OrderLead,
    Product,
    ProductFact,
    ProductView,
    ShopConversation,
    ShopInstruction,
    ShopUsage,
    TokenUsage,
)


def _open_discussion(
    session: Session,
    conversation_id: int | None,
) -> tuple[ShopConversation, OrderLead, list[DiscussionTurn]]:
    if conversation_id is None:
        conversation = ShopConversation(shop_id=DEMO_SHOP_ID)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        if conversation.id is None:
            raise RuntimeError("Discussion was not saved")
        lead = OrderLead(conversation_id=conversation.id, shop_id=DEMO_SHOP_ID)
        session.add(lead)
        session.commit()
        return conversation, lead, []
    return _load_discussion(session, conversation_id)


def _load_discussion(
    session: Session,
    conversation_id: int,
) -> tuple[ShopConversation, OrderLead, list[DiscussionTurn]]:
    conversation = session.get(ShopConversation, conversation_id)
    if conversation is None or conversation.shop_id != DEMO_SHOP_ID:
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = session.exec(
        select(OrderLead).where(OrderLead.conversation_id == conversation_id)
    ).first()
    if lead is None or conversation.id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    turns = list(
        session.exec(
            select(DiscussionTurn)
            .where(DiscussionTurn.conversation_id == conversation_id)
            .order_by(DiscussionTurn.id)
        ).all()
    )
    return conversation, lead, turns


def _product_view(session: Session, product: Product) -> ProductView:
    if product.id is None:
        raise RuntimeError("Saved product is missing an id")
    facts = session.exec(select(ProductFact).where(ProductFact.product_id == product.id)).all()
    return ProductView(
        id=product.id,
        sku=product.sku,
        shop_id=product.shop_id,
        name=product.name,
        description=product.description,
        price_tnd=product.price_tnd,
        availability=product.availability.value,
        facts=[ApprovedFact(label=fact.label, value=fact.value) for fact in facts],
    )


def _instruction_view(
    row: ShopInstruction,
    removed: list[str] | None = None,
    added: list[str] | None = None,
) -> InstructionView:
    content = row.content()
    if row.id is None:
        raise RuntimeError("Stored instruction is missing an id")
    return InstructionView(
        id=row.id,
        source_text=row.source_text,
        rules=content.rules,
        may_answer=content.may_answer,
        ask_seller=content.ask_seller,
        removed=removed or [],
        added=added or [],
    )


def _remember_usage(session: Session, usage: TokenUsage) -> None:
    """Add one model call to the shop's running token total."""
    row = session.exec(select(ShopUsage).where(ShopUsage.shop_id == DEMO_SHOP_ID)).first()
    if row is None:
        row = ShopUsage(shop_id=DEMO_SHOP_ID)
    row.input_tokens += usage.input_tokens
    row.output_tokens += usage.output_tokens
    row.total_tokens += usage.total_tokens
    session.add(row)


def _estimate_usd(input_tokens: int, output_tokens: int) -> str:
    """Estimate Groq cost. Defaults match the published gpt-oss-20b list price."""
    per_million = Decimal(1_000_000)
    incoming = Decimal(os.getenv("GROQ_INPUT_USD_PER_MILLION", "0.075"))
    outgoing = Decimal(os.getenv("GROQ_OUTPUT_USD_PER_MILLION", "0.30"))
    cost = (Decimal(input_tokens) * incoming + Decimal(output_tokens) * outgoing) / per_million
    return f"{cost:.4f}"


def _add_usage(first: TokenUsage, second: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        total_tokens=first.total_tokens + second.total_tokens,
    )


def _extract_usage(message: object) -> TokenUsage:
    metadata = getattr(message, "usage_metadata", None)
    if not isinstance(metadata, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=metadata.get("input_tokens", 0),
        output_tokens=metadata.get("output_tokens", 0),
        total_tokens=metadata.get("total_tokens", 0),
    )
