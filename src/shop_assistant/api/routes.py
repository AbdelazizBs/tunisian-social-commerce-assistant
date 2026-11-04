"""HTTP routes for the seller workspace."""

import json
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from shop_assistant.db import DEMO_SHOP_ID, get_session
from shop_assistant.models import (
    DiscussionSummary,
    DiscussionTurn,
    DiscussionView,
    InstructionContent,
    InstructionInput,
    InstructionView,
    OrderLead,
    PendingReply,
    Product,
    ProductFact,
    ProductInput,
    ProductStructure,
    ProductView,
    ReplyRequest,
    ReplyResponse,
    SellerAlert,
    ShopConversation,
    ShopInstruction,
    ShopPolicy,
    ShopPolicyInput,
    ShopUsage,
    TokenUsage,
    UsageView,
    WhatsAppMessage,
)
from shop_assistant.services.batch import (
    conversation_for_sender,
    draft_social,
    flush_due,
    remember_sender,
    schedule_draft,
    waiting_draft,
)
from shop_assistant.services.catalog import build_structure_messages
from shop_assistant.services.conversation import order_view
from shop_assistant.services.replies import (
    ModelNotConfigured,
    create_structured_model,
    handoff_for_attachment,
    is_social_only,
)
from shop_assistant.services.seller_instructions import (
    build_instruction_messages,
    content_from_note,
    instruction_diff,
    instruction_lines,
)
from shop_assistant.services.shop import (
    _estimate_usd,
    _extract_usage,
    _instruction_view,
    _load_discussion,
    _open_discussion,
    _product_view,
    _remember_usage,
)
from shop_assistant.services.whatsapp import inbound_messages, send_text, verify_signature

logger = logging.getLogger(__name__)
router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

@router.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "model_configured": bool(os.getenv("GROQ_API_KEY")),
    }

@router.get("/api/v1/shop", response_model=ShopPolicyInput)
def read_shop(session: SessionDep) -> ShopPolicyInput:
    row = session.get(ShopPolicy, DEMO_SHOP_ID)
    if row is None:
        return ShopPolicyInput()
    return ShopPolicyInput(
        delivery_days=row.delivery_days,
        delivery_price_tnd=row.delivery_price_tnd,
    )


@router.put("/api/v1/shop", response_model=ShopPolicyInput)
def save_shop(payload: ShopPolicyInput, session: SessionDep) -> ShopPolicyInput:
    row = session.get(ShopPolicy, DEMO_SHOP_ID)
    if row is None:
        row = ShopPolicy(shop_id=DEMO_SHOP_ID)
    row.delivery_days = payload.delivery_days
    row.delivery_price_tnd = payload.delivery_price_tnd
    session.add(row)
    session.commit()
    return payload


@router.get("/api/v1/products", response_model=list[ProductView])
def list_products(session: SessionDep) -> list[ProductView]:
    products = list(session.exec(select(Product).where(Product.shop_id == DEMO_SHOP_ID)).all())
    return [_product_view(session, product) for product in products]

@router.post("/api/v1/products/structure", response_model=ProductStructure)
def structure_product(product_input: ProductInput, session: SessionDep) -> ProductStructure:
    if not product_input.description.strip():
        return ProductStructure(facts=[])
    try:
        model = create_structured_model(ProductStructure)
    except ModelNotConfigured as exc:
        raise HTTPException(
            status_code=503,
            detail="Product structuring is unavailable until GROQ_API_KEY is configured.",
        ) from exc
    try:
        result = model.invoke(
            build_structure_messages(product_input.name, product_input.description)
        )
        if result["parsing_error"] is not None or result["parsed"] is None:
            raise ValueError("The model output did not match the product structure schema")
        _remember_usage(session, _extract_usage(result["raw"]))
        return ProductStructure.model_validate(result["parsed"])
    except ValueError:
        logger.warning("Product structure generation failed output validation")
        raise HTTPException(
            status_code=502,
            detail="The description could not be structured. Please rephrase it.",
        ) from None
    except Exception:
        logger.warning("Product structure generation failed")
        raise HTTPException(
            status_code=502,
            detail="Reading the description failed. Please retry.",
        ) from None

@router.put("/api/v1/products/{sku}", response_model=ProductView)
def save_product(sku: str, product_input: ProductInput, session: SessionDep) -> ProductView:
    if not sku.strip() or len(sku) > 80:
        raise HTTPException(status_code=422, detail="SKU must contain 1 to 80 characters")

    product = session.exec(
        select(Product).where(
            Product.shop_id == DEMO_SHOP_ID,
            Product.sku == sku,
        )
    ).first()
    fields = product_input.model_dump(exclude={"facts"})
    if product is None:
        product = Product(sku=sku, shop_id=DEMO_SHOP_ID, **fields)
    else:
        for key, value in fields.items():
            setattr(product, key, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    if product.id is None:
        raise RuntimeError("Saved product is missing an id")
    old_facts = session.exec(
        select(ProductFact).where(ProductFact.product_id == product.id)
    ).all()
    for old in old_facts:
        session.delete(old)
    for fact in product_input.facts:
        session.add(ProductFact(
            product_id=product.id,
            shop_id=DEMO_SHOP_ID,
            label=fact.label.strip(),
            value=fact.value.strip(),
        ))
    session.commit()
    return _product_view(session, product)

@router.delete("/api/v1/products/{sku}", status_code=204)
def delete_product(sku: str, session: SessionDep) -> None:
    product = session.exec(
        select(Product).where(Product.shop_id == DEMO_SHOP_ID, Product.sku == sku)
    ).first()
    if product is None or product.id is None:
        raise HTTPException(status_code=404, detail="Product not found")
    facts = session.exec(select(ProductFact).where(ProductFact.product_id == product.id)).all()
    for fact in facts:
        session.delete(fact)
    session.delete(product)
    session.commit()

@router.get("/api/v1/instructions", response_model=list[InstructionView])
def list_instructions(session: SessionDep) -> list[InstructionView]:
    rows = session.exec(
        select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)
    ).all()
    return [_instruction_view(row) for row in rows]

@router.post("/api/v1/instructions", response_model=InstructionView)
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

    previous_rows = list(
        session.exec(
            select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)
        ).all()
    )
    previous_text = "\n".join(row.source_text for row in previous_rows)
    content = content_from_note(source_text)
    if len(source_text) <= 1200:
        try:
            result = model.invoke(build_instruction_messages(source_text))
            if result["parsing_error"] is None and result["parsed"] is not None:
                parsed = InstructionContent.model_validate(result["parsed"])
                if parsed.rules or parsed.may_answer:
                    content = parsed
                    _remember_usage(session, _extract_usage(result["raw"]))
        except Exception as exc:
            logger.warning(
                "Seller instruction generation failed type=%s status=%s",
                type(exc).__name__,
                getattr(exc, "status_code", None),
            )

    removed, added = instruction_diff(
        instruction_lines(previous_text),
        instruction_lines(source_text),
    )
    for old in previous_rows:
        session.delete(old)
    row = ShopInstruction(
        shop_id=DEMO_SHOP_ID,
        source_text=source_text,
        content_json=content.model_dump_json(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _instruction_view(row, removed, added)

@router.delete("/api/v1/instructions/{instruction_id}", status_code=204)
def delete_instruction(instruction_id: int, session: SessionDep) -> None:
    row = session.get(ShopInstruction, instruction_id)
    if row is None or row.shop_id != DEMO_SHOP_ID:
        raise HTTPException(status_code=404, detail="Instruction not found")
    session.delete(row)
    session.commit()

@router.post("/api/v1/alerts/seen", status_code=204)
def mark_alerts_seen(session: SessionDep) -> None:
    rows = session.exec(
        select(SellerAlert).where(SellerAlert.shop_id == DEMO_SHOP_ID, SellerAlert.priority == True)  # noqa: E712
    ).all()
    for row in rows:
        row.priority = False
        session.add(row)
    session.commit()

@router.get("/api/v1/alerts", response_model=list[SellerAlert])
def list_alerts(session: SessionDep) -> list[SellerAlert]:
    return list(
        session.exec(
            select(SellerAlert)
            .where(SellerAlert.shop_id == DEMO_SHOP_ID, SellerAlert.priority == True)  # noqa: E712
            .order_by(SellerAlert.id.desc())
        ).all()
    )

@router.get("/api/v1/steps")
def list_steps() -> list[dict[str, str | int | float | bool | None]]:
    from shop_assistant.services.batch import recent_steps

    return recent_steps()


@router.get("/api/v1/conversations", response_model=list[DiscussionSummary])
def list_conversations(session: SessionDep) -> list[DiscussionSummary]:
    rows = session.exec(
        select(ShopConversation)
        .where(ShopConversation.shop_id == DEMO_SHOP_ID)
        .order_by(ShopConversation.id.desc())
    ).all()
    summaries = []
    for row in rows:
        if row.id is None:
            continue
        turns = session.exec(
            select(DiscussionTurn).where(DiscussionTurn.conversation_id == row.id)
        ).all()
        preview = turns[-1].text if turns else "Empty"
        summaries.append(DiscussionSummary(id=row.id, preview=preview[:120], channel="test"))
    return summaries

@router.delete("/api/v1/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, session: SessionDep) -> None:
    conversation = session.get(ShopConversation, conversation_id)
    if conversation is None or conversation.shop_id != DEMO_SHOP_ID:
        raise HTTPException(status_code=404, detail="Conversation not found")
    for model in (DiscussionTurn, OrderLead, SellerAlert, PendingReply):
        rows = session.exec(select(model).where(model.conversation_id == conversation_id)).all()
        for row in rows:
            session.delete(row)
    session.delete(conversation)
    session.commit()


@router.post("/api/v1/conversations/{conversation_id}/reply")
def seller_reply(
    conversation_id: int, payload: dict[str, str], session: SessionDep
) -> dict[str, str]:
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Write a reply first")
    _load_discussion(session, conversation_id)
    session.add(DiscussionTurn(
        conversation_id=conversation_id, role="seller", text=text[:4000]
    ))
    session.commit()
    return {"status": "saved"}

@router.get("/api/v1/conversations/{conversation_id}", response_model=DiscussionView)
def get_conversation(conversation_id: int, session: SessionDep) -> DiscussionView:
    flush_due(session)
    conversation, lead, turns = _load_discussion(session, conversation_id)
    return DiscussionView(
        conversation_id=conversation.id or conversation_id,
        turns=[{"role": turn.role, "text": turn.text} for turn in turns],
        order=order_view(lead),
    )

@router.post("/api/v1/replies/draft", response_model=ReplyResponse)
def draft_reply(request: ReplyRequest, session: SessionDep) -> ReplyResponse:
    if request.attachment is not None:
        return ReplyResponse(
            draft=handoff_for_attachment(request.attachment),
            model="none",
            latency_ms=0,
            usage=TokenUsage(),
        )

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Reply drafting is unavailable until GROQ_API_KEY is configured.",
        )
    conversation, lead, earlier = _open_discussion(session, request.conversation_id)
    if conversation.id is None:
        raise RuntimeError("Discussion was not saved")
    session.add(DiscussionTurn(
        conversation_id=conversation.id, role="buyer", text=request.message.strip()
    ))
    unanswered = earlier[-1].role == "buyer" if earlier else False
    if is_social_only(request.message) and not unanswered:
        draft = draft_social(session, request.message.strip(), earlier, lead)
        saved = (draft.reply_text or draft.seller_question).strip()
        if saved:
            session.add(DiscussionTurn(
                conversation_id=conversation.id, role="draft", text=saved
            ))
        session.commit()
        return ReplyResponse(
            draft=draft,
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            latency_ms=0,
            usage=TokenUsage(),
            conversation_id=conversation.id,
            order=order_view(lead),
            waiting=False,
        )
    session.commit()
    schedule_draft(conversation.id)
    return ReplyResponse(
        draft=waiting_draft(),
        model="waiting",
        latency_ms=0,
        usage=TokenUsage(),
        conversation_id=conversation.id,
        order=order_view(lead),
        waiting=True,
    )

@router.get("/api/v1/usage", response_model=UsageView)
def shop_usage(session: SessionDep) -> UsageView:
    row = session.exec(select(ShopUsage).where(ShopUsage.shop_id == DEMO_SHOP_ID)).first()
    incoming = row.input_tokens if row else 0
    outgoing = row.output_tokens if row else 0
    total = row.total_tokens if row else 0
    return UsageView(
        input_tokens=incoming,
        output_tokens=outgoing,
        total_tokens=total,
        estimated_usd=_estimate_usd(incoming, outgoing),
    )

@router.get("/api/v1/whatsapp/webhook")
def whatsapp_verify(request: Request) -> int:
    params = request.query_params
    token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    mode_ok = params.get("hub.mode") == "subscribe"
    token_ok = params.get("hub.verify_token") == token
    if not token or not mode_ok or not token_ok:
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    challenge = params.get("hub.challenge")
    if challenge is None or not challenge.isdigit():
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return int(challenge)

@router.post("/api/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    secret = os.getenv("WHATSAPP_APP_SECRET")
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not secret or not verify_signature(body, signature, secret):
        raise HTTPException(status_code=403, detail="Webhook signature was rejected")
    payload = json.loads(body or b"{}")
    scheduled: list[int] = []
    for item in inbound_messages(payload):
        existing = session.exec(
            select(WhatsAppMessage).where(
                WhatsAppMessage.wa_message_id == item["wa_message_id"]
            )
        ).first()
        if existing is not None:
            continue
        session.add(WhatsAppMessage(shop_id=DEMO_SHOP_ID, **item))
        text = item["text"].strip()
        if item["kind"] == "text" and text:
            try:
                conversation, _lead, _turns = _open_discussion(
                    session, conversation_for_sender(item["sender"])
                )
            except HTTPException:
                conversation, _lead, _turns = _open_discussion(session, None)
            if conversation.id is not None:
                session.add(DiscussionTurn(
                    conversation_id=conversation.id, role="buyer", text=text
                ))
                remember_sender(item["sender"], conversation.id)
                scheduled.append(conversation.id)
    session.commit()
    if os.getenv("GROQ_API_KEY"):
        for conversation_id in scheduled:
            schedule_draft(conversation_id)
    return {"status": "ok"}

@router.get("/api/v1/whatsapp/inbox")
def whatsapp_inbox(session: SessionDep) -> list[WhatsAppMessage]:
    return list(
        session.exec(
            select(WhatsAppMessage)
            .where(WhatsAppMessage.shop_id == DEMO_SHOP_ID)
            .order_by(WhatsAppMessage.id.desc())
        ).all()
    )

@router.post("/api/v1/whatsapp/messages/{message_id}/send")
def whatsapp_send(
    message_id: int, payload: dict[str, str], session: SessionDep
) -> dict[str, str]:
    row = session.get(WhatsAppMessage, message_id)
    text = (payload.get("text") or "").strip()
    if row is None or row.shop_id != DEMO_SHOP_ID:
        raise HTTPException(status_code=404, detail="WhatsApp message not found")
    if not text:
        raise HTTPException(status_code=422, detail="Write the reply before sending it")
    try:
        send_text(row.sender, text)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID before sending.",
        ) from exc
    except Exception as exc:
        logger.warning("WhatsApp send failed")
        raise HTTPException(
            status_code=502, detail="WhatsApp did not accept the message."
        ) from exc
    row.status = "sent"
    session.add(row)
    session.commit()
    return {"status": "sent"}
