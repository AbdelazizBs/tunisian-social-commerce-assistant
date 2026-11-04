"""Shop records and API shapes. Other modules import these; they do not declare them again."""

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Field as SqlField
from sqlmodel import SQLModel


class Availability(StrEnum):
    """Whether a product can be sold."""

    AVAILABLE = "available"
    SOLD_OUT = "sold_out"
    UNKNOWN = "unknown"


class Product(SQLModel, table=True):
    """One seller-approved product in a shop."""

    id: int | None = SqlField(default=None, primary_key=True)
    sku: str = SqlField(index=True, unique=True, max_length=80)
    shop_id: str = SqlField(index=True, max_length=80)
    name: str = SqlField(max_length=160)
    description: str = SqlField(default="", max_length=2000)
    price_tnd: Decimal | None = SqlField(default=None, ge=0, max_digits=10, decimal_places=3)
    availability: Availability = SqlField(default=Availability.UNKNOWN)


class ProductFact(SQLModel, table=True):
    """One labeled detail taken from a product description."""

    id: int | None = SqlField(default=None, primary_key=True)
    product_id: int = SqlField(index=True)
    shop_id: str = SqlField(index=True, max_length=80)
    label: str = SqlField(max_length=80)
    value: str = SqlField(max_length=240)


class ApprovedFact(BaseModel):
    """A fact the seller has confirmed."""

    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=240)


class ProductStructure(BaseModel):
    """Facts the model read from a product description."""

    facts: list[ApprovedFact] = Field(
        description="Details explicitly written in the description. Empty when none are written."
    )


class ShopPolicy(SQLModel, table=True):
    """Delivery days and price. These are shop data, not seller instructions."""

    shop_id: str = SqlField(primary_key=True, max_length=80)
    delivery_days: int | None = SqlField(default=None, ge=0)
    delivery_price_tnd: Decimal | None = SqlField(
        default=None, ge=0, max_digits=10, decimal_places=3,
    )


class ShopPolicyInput(BaseModel):
    """The delivery facts the seller saves."""

    delivery_days: int | None = Field(default=None, ge=0, le=60)
    delivery_price_tnd: Decimal | None = Field(default=None, ge=0)


class ProductView(BaseModel):
    """A product plus its facts, as the page reads it."""

    id: int
    sku: str
    shop_id: str
    name: str
    description: str
    price_tnd: Decimal | None
    availability: str
    facts: list[ApprovedFact]


class ShopConversation(SQLModel, table=True):
    """One buyer thread for a shop."""

    id: int | None = SqlField(default=None, primary_key=True)
    shop_id: str = SqlField(index=True, max_length=80)


class PendingReply(SQLModel, table=True):
    """When the quiet window ends for one thread. Survives an API reload."""

    conversation_id: int = SqlField(primary_key=True)
    due_at: float


class DiscussionTurn(SQLModel, table=True):
    """One buyer line or assistant draft inside a thread."""

    id: int | None = SqlField(default=None, primary_key=True)
    conversation_id: int = SqlField(index=True)
    role: str = SqlField(max_length=20)
    text: str = SqlField(max_length=4000)


class SellerAlert(SQLModel, table=True):
    """A priority flag for the seller. The notice does not repeat the buyer text."""

    id: int | None = SqlField(default=None, primary_key=True)
    conversation_id: int = SqlField(index=True)
    shop_id: str = SqlField(index=True, max_length=80)
    notice: str = SqlField(max_length=500)
    priority: bool = SqlField(default=True)
    flagged: bool = SqlField(default=True)


class OrderLead(SQLModel, table=True):
    """Product, size, phone, and address collected for one thread."""

    id: int | None = SqlField(default=None, primary_key=True)
    conversation_id: int = SqlField(index=True, unique=True)
    shop_id: str = SqlField(max_length=80)
    product_name: str = SqlField(default="", max_length=160)
    size: str = SqlField(default="", max_length=40)
    phone: str = SqlField(default="", max_length=40)
    address: str = SqlField(default="", max_length=300)


class OrderView(BaseModel):
    """Saved order details and the names of the ones still missing."""

    product_name: str
    size: str
    phone: str
    address: str
    missing: list[str]


class DiscussionSummary(BaseModel):
    """A thread the seller can open."""

    id: int
    preview: str
    channel: str = "test"


class DiscussionView(BaseModel):
    """A thread the page can show again."""

    conversation_id: int
    turns: list[dict[str, str]]
    order: OrderView


class InstructionContent(BaseModel):
    """A seller note split into rules, answers, and questions for the seller."""

    rules: list[str] = Field(description="How the assistant should speak and behave")
    may_answer: list[str] = Field(
        description=(
            "Facts and everyday situations the assistant should answer itself, "
            "without asking the seller"
        )
    )
    ask_seller: list[str] = Field(
        description="Cases that still need the seller. Ordinary greetings do not belong here."
    )


class ShopInstruction(SQLModel, table=True):
    """The seller's note and the structured skill saved from it."""

    id: int | None = SqlField(default=None, primary_key=True)
    shop_id: str = SqlField(index=True, max_length=80)
    source_text: str = SqlField(max_length=12000)
    content_json: str = SqlField(max_length=24000)

    def content(self) -> InstructionContent:
        """Read the stored skill back into its three lists."""
        return InstructionContent.model_validate_json(self.content_json)


class InstructionView(BaseModel):
    """A saved instruction, including which lines were removed or added."""

    id: int
    source_text: str
    rules: list[str]
    may_answer: list[str]
    ask_seller: list[str]
    removed: list[str] = []
    added: list[str] = []


class AttachmentKind(StrEnum):
    """A buyer share the assistant does not interpret."""

    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"


class ReplyDraft(BaseModel):
    """The structured reply the model must return."""

    reply_text: str = Field(
        description="Short draft in the buyer's language; empty when handoff is needed"
    )
    customer_intent: Literal["social_conversation", "shop_question"] = Field(
        description=(
            "Use social_conversation for pleasantries, jokes, laughter, insults, random "
            "letters, and anything you cannot read as a shop request. Use shop_question "
            "only for a product, order, delivery, price, stock, or policy fact."
        )
    )
    matched_product_ids: list[int] = Field(description="IDs of approved products used as evidence")
    used_instruction_ids: list[int] = Field(
        default_factory=list,
        description="IDs of seller instructions that support this answer. Empty when unused.",
    )
    needs_seller: bool = Field(
        description=(
            "True only when a shop fact is missing from both the catalog and the seller "
            "instructions. False for conversation and for facts the seller already taught."
        )
    )
    seller_question: str = Field(
        description=(
            "Question for the seller when a shop fact is missing. "
            "Use an empty string when the seller is not needed. "
            "Do not omit this field."
        ),
    )
    order_product: str = Field(
        description=(
            "Product the buyer wants. Keep the product from earlier in the "
            "discussion when this message does not change it. Empty if none yet."
        )
    )
    order_size: str = Field(
        description="Size the buyer gave, such as S, M, or L. Empty if not given yet."
    )
    order_phone: str = Field(description="Buyer phone number. Empty if not given yet.")
    order_address: str = Field(description="Delivery address. Empty if not given yet.")


class SafetyFlag(BaseModel):
    """Whether the buyer message should go straight to the seller."""

    tell_seller: bool = Field(
        description=(
            "True when the buyer insults, harasses, uses sexual abuse, threatens "
            "someone, or asks for something illegal. False for greetings, shop "
            "questions, prices, and delivery. Judge the meaning in any language."
        )
    )


class CatalogNeed(BaseModel):
    """Whether this message needs product records in the prompt."""

    needs_catalog: bool = Field(
        description=(
            "True only when the buyer is asking about a product, category, color, "
            "size, price, or stock. False for greetings, small talk, thanks, and "
            "questions that are not about products."
        )
    )


class TokenUsage(BaseModel):
    """Token counts reported for one model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ReplyResponse(BaseModel):
    """The draft, timing, and saved order returned to the page."""

    draft: ReplyDraft
    model: str
    latency_ms: int
    usage: TokenUsage
    conversation_id: int | None = None
    order: OrderView | None = None
    priority: bool = False
    flagged: bool = False
    waiting: bool = False


class ShopUsage(SQLModel, table=True):
    """Running token totals for one shop."""

    id: int | None = SqlField(default=None, primary_key=True)
    shop_id: str = SqlField(index=True, unique=True, max_length=80)
    input_tokens: int = SqlField(default=0)
    output_tokens: int = SqlField(default=0)
    total_tokens: int = SqlField(default=0)


class UsageView(BaseModel):
    """Tokens used so far and an estimated provider cost."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_usd: str


class WhatsAppMessage(SQLModel, table=True):
    """One inbound WhatsApp message waiting for the seller."""

    id: int | None = SqlField(default=None, primary_key=True)
    shop_id: str = SqlField(index=True, max_length=80)
    wa_message_id: str = SqlField(unique=True, max_length=180)
    sender: str = SqlField(max_length=40)
    kind: str = SqlField(max_length=20)
    text: str = SqlField(default="", max_length=4000)
    status: str = SqlField(default="received", max_length=20)
