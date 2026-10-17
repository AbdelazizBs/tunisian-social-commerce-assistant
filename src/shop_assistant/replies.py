import json
import os
from typing import Any

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from shop_assistant.catalog import Product


class ReplyDraft(BaseModel):
    reply_text: str = Field(
        description="Short draft in the buyer's language; empty when handoff is needed"
    )
    matched_product_ids: list[int] = Field(description="IDs of approved products used as evidence")
    needs_seller: bool = Field(description="True when the catalog cannot support a safe answer")
    seller_question: str | None = Field(
        description="The unanswered question for the seller, or null when not needed"
    )


class ModelNotConfigured(Exception):
    pass


SYSTEM_PROMPT = """You draft concise replies for a Tunisian online shop.
Mirror the buyer's language and writing style when reliable: Tunisian Arabic, Arabic,
French, Arabic-French, or Arabizi. Never claim to be human. Use only the approved
catalog facts included below. Reference the IDs of products used as evidence.
If the approved facts do not answer the buyer, return an empty reply_text, set
needs_seller=true, and ask the seller a concise question. Never invent stock, price,
delivery time, policy, or order acceptance. This is a draft for the seller; do not
send anything to a customer.
"""


def create_reply_model(*, api_key: str | None = None) -> Any:
    token = api_key or os.getenv("GROQ_API_KEY")
    if not token:
        raise ModelNotConfigured

    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        api_key=token,
        temperature=0.1,
        timeout=20,
        max_retries=1,
    )
    return model.with_structured_output(
        ReplyDraft,
        method="json_schema",
        strict=True,
        include_raw=True,
    )


def build_reply_messages(products: list[Product], buyer_message: str) -> list[tuple[str, str]]:
    catalog_json = json.dumps(
        [
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "description": product.description,
                "price_tnd": str(product.price_tnd) if product.price_tnd is not None else None,
                "availability": product.availability.value,
            }
            for product in products
        ],
        ensure_ascii=False,
    )
    return [
        ("system", f"{SYSTEM_PROMPT}\nApproved catalog: {catalog_json}"),
        ("human", buyer_message),
    ]


def validate_evidence(draft: ReplyDraft, products: list[Product]) -> ReplyDraft:
    allowed_ids = {product.id for product in products if product.id is not None}
    if any(product_id not in allowed_ids for product_id in draft.matched_product_ids):
        raise ValueError("The model cited a product outside the approved catalog")

    # A product answer without a catalog citation cannot be trusted, even if it sounds plausible.
    if not draft.needs_seller and not draft.matched_product_ids:
        return ReplyDraft(
            reply_text="",
            matched_product_ids=[],
            needs_seller=True,
            seller_question=(
                "I could not verify this from the approved product information. "
                "What should I tell the buyer?"
            ),
        )
    return draft
