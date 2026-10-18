import logging
import os
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from pydantic import Field as PydanticField
from sqlmodel import Session, SQLModel, create_engine, select

from shop_assistant.catalog import Product, ProductInput
from shop_assistant.conversation import (
    DiscussionTurn,
    OrderLead,
    OrderView,
    ShopConversation,
    format_discussion,
    order_view,
    remember_order,
)
from shop_assistant.replies import (
    AttachmentKind,
    CatalogNeed,
    ModelNotConfigured,
    ReplyDraft,
    build_catalog_need_messages,
    build_reply_messages,
    create_reply_model,
    create_structured_model,
    handoff_for_attachment,
    validate_evidence,
)
from shop_assistant.retrieval import products_for_question
from shop_assistant.seller_instructions import (
    InstructionContent,
    ShopInstruction,
    build_instruction_messages,
)

logger = logging.getLogger(__name__)
DEMO_SHOP_ID = "demo-shop"


class ReplyRequest(BaseModel):
    message: str = PydanticField(default="", max_length=4000)
    attachment: AttachmentKind | None = None
    conversation_id: int | None = None

    @model_validator(mode="after")
    def require_buyer_input(self) -> "ReplyRequest":
        if self.attachment is None and not self.message.strip():
            raise ValueError("A buyer message or a non-text share is required")
        return self


class InstructionInput(BaseModel):
    text: str = PydanticField(min_length=1, max_length=4000)


class InstructionView(BaseModel):
    id: int
    source_text: str
    rules: list[str]
    may_answer: list[str]
    ask_seller: list[str]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ReplyResponse(BaseModel):
    draft: ReplyDraft
    model: str
    latency_ms: int
    usage: TokenUsage
    conversation_id: int | None = None
    order: OrderView | None = None


class DiscussionView(BaseModel):
    conversation_id: int
    turns: list[dict[str, str]]
    order: OrderView


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///./.local/app.db")
    if url.startswith("sqlite") and ":memory:" not in url:
        Path(".local").mkdir(exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        SQLModel.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Tunisian Social Commerce Assistant",
        version="0.1.0",
        description="Local, seller-reviewed reply copilot. No messages are sent.",
        lifespan=lifespan,
    )

    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    SessionDep = Annotated[Session, Depends(get_session)]

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "model_configured": bool(os.getenv("GROQ_API_KEY")),
        }

    @app.get("/api/v1/products", response_model=list[Product])
    def list_products(session: SessionDep) -> list[Product]:
        return list(session.exec(select(Product).where(Product.shop_id == DEMO_SHOP_ID)).all())

    @app.put("/api/v1/products/{sku}", response_model=Product)
    def save_product(sku: str, product_input: ProductInput, session: SessionDep) -> Product:
        if not sku.strip() or len(sku) > 80:
            raise HTTPException(status_code=422, detail="SKU must contain 1 to 80 characters")

        product = session.exec(
            select(Product).where(
                Product.shop_id == DEMO_SHOP_ID,
                Product.sku == sku,
            )
        ).first()
        if product is None:
            product = Product(sku=sku, shop_id=DEMO_SHOP_ID, **product_input.model_dump())
        else:
            for key, value in product_input.model_dump().items():
                setattr(product, key, value)

        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    @app.get("/api/v1/instructions", response_model=list[InstructionView])
    def list_instructions(session: SessionDep) -> list[InstructionView]:
        rows = session.exec(
            select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)
        ).all()
        return [_instruction_view(row) for row in rows]

    @app.post("/api/v1/instructions", response_model=InstructionView)
    def add_instruction(request: InstructionInput, session: SessionDep) -> InstructionView:
        source_text = request.text.strip()
        if not source_text:
            raise HTTPException(status_code=422, detail="Instruction text is required")
        try:
            model = create_structured_model(InstructionContent)
        except ModelNotConfigured as exc:
            raise HTTPException(
                status_code=503,
                detail="Instructions are unavailable until GROQ_API_KEY is configured.",
            ) from exc

        try:
            result = model.invoke(build_instruction_messages(source_text))
            if result["parsing_error"] is not None or result["parsed"] is None:
                raise ValueError("The model output did not match the instruction schema")
            content = InstructionContent.model_validate(result["parsed"])
            if not content.rules and not content.may_answer:
                raise ValueError("The note did not contain usable instructions")
        except ValueError:
            logger.warning("Seller instruction generation failed output validation")
            raise HTTPException(
                status_code=502,
                detail="That note could not be turned into instructions. Please rephrase it.",
            ) from None
        except Exception as exc:
            logger.warning(
                "Seller instruction generation failed type=%s status=%s",
                type(exc).__name__,
                getattr(exc, "status_code", None),
            )
            raise HTTPException(
                status_code=502,
                detail="Saving the instruction failed. Please retry.",
            ) from None

        row = ShopInstruction(
            shop_id=DEMO_SHOP_ID,
            source_text=source_text,
            content_json=content.model_dump_json(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _instruction_view(row)

    @app.delete("/api/v1/instructions/{instruction_id}", status_code=204)
    def delete_instruction(instruction_id: int, session: SessionDep) -> None:
        row = session.get(ShopInstruction, instruction_id)
        if row is None or row.shop_id != DEMO_SHOP_ID:
            raise HTTPException(status_code=404, detail="Instruction not found")
        session.delete(row)
        session.commit()

    @app.get("/api/v1/conversations/{conversation_id}", response_model=DiscussionView)
    def get_conversation(conversation_id: int, session: SessionDep) -> DiscussionView:
        conversation, lead, turns = _load_discussion(session, conversation_id)
        return DiscussionView(
            conversation_id=conversation.id or conversation_id,
            turns=[{"role": turn.role, "text": turn.text} for turn in turns],
            order=order_view(lead),
        )

    @app.post("/api/v1/replies/draft", response_model=ReplyResponse)
    def draft_reply(request: ReplyRequest, session: SessionDep) -> ReplyResponse:
        if request.attachment is not None:
            return ReplyResponse(
                draft=handoff_for_attachment(request.attachment),
                model="none",
                latency_ms=0,
                usage=TokenUsage(),
            )

        products = list(
            session.exec(select(Product).where(Product.shop_id == DEMO_SHOP_ID)).all()
        )
        instructions = list(
            session.exec(
                select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)
            ).all()
        )

        try:
            route_model = create_structured_model(CatalogNeed)
            model = create_reply_model()
        except ModelNotConfigured as exc:
            raise HTTPException(
                status_code=503,
                detail="Reply drafting is unavailable until GROQ_API_KEY is configured.",
            ) from exc

        conversation, lead, turns = _open_discussion(session, request.conversation_id)
        history = format_discussion(turns)
        order_note = (
            f"product: {lead.product_name}\nsize: {lead.size}\n"
            f"phone: {lead.phone}\naddress: {lead.address}"
        ).strip()
        started = time.perf_counter()
        try:
            route_result = route_model.invoke(
                build_catalog_need_messages(request.message, history)
            )
            if route_result["parsing_error"] is not None:
                raise ValueError("The model output did not match the catalog decision schema")
            needs_catalog = CatalogNeed.model_validate(route_result["parsed"]).needs_catalog
            retrieved_products = products_for_question(products, needs_catalog)
            result = model.invoke(
                build_reply_messages(
                    retrieved_products,
                    request.message,
                    instructions,
                    history,
                    order_note,
                )
            )
            if result["parsing_error"] is not None:
                raise ValueError("The model output did not match the reply schema")
            draft = validate_evidence(
                ReplyDraft.model_validate(result["parsed"]),
                retrieved_products,
                instructions,
                lead.product_name,
                request.message,
            )
        except ValueError:
            logger.warning("Model reply failed output or catalog-evidence validation")
            raise HTTPException(
                status_code=502,
                detail=(
                    "The draft could not be verified against approved products. "
                    "Please review it manually."
                ),
            ) from None
        except Exception as exc:
            # Log the provider's own error text, not the buyer message or the prompt.
            body = getattr(exc, "body", None)
            provider_message = ""
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict):
                    provider_message = str(error.get("message", ""))[:300]
            logger.warning(
                "Model reply generation failed type=%s status=%s provider=%s",
                type(exc).__name__,
                getattr(exc, "status_code", None),
                provider_message,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Reply drafting failed. No message was sent; "
                    "please answer manually or retry."
                ),
            ) from None

        usage = _add_usage(_extract_usage(route_result["raw"]), _extract_usage(result["raw"]))
        saved_text = draft.reply_text or draft.seller_question
        if conversation.id is None:
            raise RuntimeError("Discussion was not saved")
        session.add(DiscussionTurn(
            conversation_id=conversation.id, role="buyer", text=request.message.strip()
        ))
        if saved_text.strip():
            session.add(DiscussionTurn(
                conversation_id=conversation.id, role="draft", text=saved_text.strip()
            ))
        remember_order(
            lead,
            draft.order_product,
            draft.order_size,
            draft.order_phone,
            draft.order_address,
        )
        session.add(lead)
        session.commit()
        return ReplyResponse(
            draft=draft,
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            latency_ms=round((time.perf_counter() - started) * 1000),
            usage=usage,
            conversation_id=conversation.id,
            order=order_view(lead),
        )

    return app


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


def _instruction_view(row: ShopInstruction) -> InstructionView:
    content = row.content()
    if row.id is None:
        raise RuntimeError("Stored instruction is missing an id")
    return InstructionView(
        id=row.id,
        source_text=row.source_text,
        rules=content.rules,
        may_answer=content.may_answer,
        ask_seller=content.ask_seller,
    )


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


app = create_app()
