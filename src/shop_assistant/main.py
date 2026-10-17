import logging
import os
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlmodel import Session, SQLModel, create_engine, select

from shop_assistant.catalog import Product, ProductInput
from shop_assistant.replies import (
    ModelNotConfigured,
    ReplyDraft,
    build_reply_messages,
    create_reply_model,
    validate_evidence,
)

logger = logging.getLogger(__name__)
DEMO_SHOP_ID = "demo-shop"


class ReplyRequest(BaseModel):
    message: str = PydanticField(min_length=1, max_length=4000)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ReplyResponse(BaseModel):
    draft: ReplyDraft
    model: str
    latency_ms: int
    usage: TokenUsage


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

    @app.post("/api/v1/replies/draft", response_model=ReplyResponse)
    def draft_reply(request: ReplyRequest, session: SessionDep) -> ReplyResponse:
        products = list(
            session.exec(select(Product).where(Product.shop_id == DEMO_SHOP_ID)).all()
        )
        if not products:
            return ReplyResponse(
                draft=ReplyDraft(
                    reply_text="",
                    matched_product_ids=[],
                    needs_seller=True,
                    seller_question="Add an approved product card before drafting product replies.",
                ),
                model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                latency_ms=0,
                usage=TokenUsage(),
            )

        try:
            model = create_reply_model()
        except ModelNotConfigured as exc:
            raise HTTPException(
                status_code=503,
                detail="Reply drafting is unavailable until GROQ_API_KEY is configured.",
            ) from exc

        started = time.perf_counter()
        try:
            result = model.invoke(build_reply_messages(products, request.message))
            if result["parsing_error"] is not None:
                raise ValueError("The model output did not match the reply schema")
            draft = validate_evidence(ReplyDraft.model_validate(result["parsed"]), products)
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
            # Provider exceptions can contain message contents; log only safe error metadata.
            logger.warning(
                "Model reply generation failed type=%s status=%s",
                type(exc).__name__,
                getattr(exc, "status_code", None),
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Reply drafting failed. No message was sent; "
                    "please answer manually or retry."
                ),
            ) from None

        usage = _extract_usage(result["raw"])
        return ReplyResponse(
            draft=draft,
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            latency_ms=round((time.perf_counter() - started) * 1000),
            usage=usage,
        )

    return app


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
