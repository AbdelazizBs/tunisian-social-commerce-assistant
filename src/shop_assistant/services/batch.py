"""Hold a burst of buyer lines, then draft once.

WhatsApp sends one webhook per bubble and must get a fast 200. A quiet
window is the right place to join those bubbles. Each new line resets the
window. When it ends, the agent sees one message.
"""

import logging
import os
import threading
import time
from collections import deque

from fastapi import HTTPException
from sqlmodel import Session, select

from shop_assistant import db
from shop_assistant.db import DEMO_SHOP_ID
from shop_assistant.models import (
    CatalogNeed,
    DiscussionTurn,
    PendingReply,
    Product,
    ProductFact,
    ReplyDraft,
    SafetyFlag,
    SellerAlert,
    ShopInstruction,
    ShopPolicy,
)
from shop_assistant.services.conversation import format_discussion, remember_order
from shop_assistant.services.replies import (
    ModelNotConfigured,
    asks_wholesale,
    build_catalog_need_messages,
    build_reply_messages,
    build_safety_messages,
    create_reply_model,
    create_structured_model,
    handoff_for_safety,
    handoff_for_wholesale,
    needs_catalog_retry,
    validate_evidence,
)
from shop_assistant.services.retrieval import products_for_question
from shop_assistant.services.shop import (
    _add_usage,
    _extract_usage,
    _load_discussion,
    _remember_usage,
)

logger = logging.getLogger(__name__)
_senders: dict[str, int] = {}


def quiet_seconds() -> int:
    """How long to wait after the latest buyer line. Zero drafts immediately."""
    raw = os.getenv("REPLY_QUIET_SECONDS", "40")
    try:
        return max(0, int(raw))
    except ValueError:
        return 40


def cancel_pending() -> None:
    """Kept so shutdown still has a hook. The wait itself is a database row."""
    return None


_steps: deque[dict[str, str | int | float | bool | None]] = deque(maxlen=200)
_step_lock = threading.Lock()
_step_id = 0


def reset_steps() -> None:
    """Drop the in-memory trace. Used by tests. Nothing is stored on disk."""
    global _step_id
    with _step_lock:
        _steps.clear()
        _step_id = 0


def recent_steps() -> list[dict[str, str | int | float | bool | None]]:
    """Newest trace lines for this process. Gone when the API stops."""
    with _step_lock:
        return list(_steps)


def step(conversation_id: int | None, name: str, detail: str = "", *, ok: bool = True) -> None:
    """Append one trace line in memory. Not written to the database."""
    global _step_id
    with _step_lock:
        _step_id += 1
        _steps.appendleft({
            "id": _step_id,
            "conversation_id": conversation_id,
            "name": name,
            "detail": detail[:500],
            "ok": ok,
            "created_at": time.time(),
        })


def schedule_draft(conversation_id: int) -> None:
    """Reset the quiet window for one thread."""
    if db.engine is None:
        return
    step(conversation_id, "waiting", f"Quiet window {quiet_seconds()}s")
    due_at = time.time() + quiet_seconds()
    with Session(db.engine) as session:
        row = session.get(PendingReply, conversation_id)
        if row is None:
            session.add(PendingReply(conversation_id=conversation_id, due_at=due_at))
        else:
            row.due_at = due_at
            session.add(row)
        session.commit()


def flush_due(session: Session) -> None:
    """Draft every thread whose quiet window has ended."""
    due = list(
        session.exec(select(PendingReply).where(PendingReply.due_at <= time.time())).all()
    )
    ids = [row.conversation_id for row in due]
    for row in due:
        session.delete(row)
    if ids:
        session.commit()
    for conversation_id in ids:
        try:
            run_collected_draft(session, conversation_id)
        except Exception as exc:
            step(conversation_id, "failed", type(exc).__name__, ok=False)
            logger.exception("Quiet-window draft failed for conversation %s", conversation_id)


def remember_sender(sender: str, conversation_id: int) -> None:
    """Keep the WhatsApp thread for the next bubble from the same number."""
    _senders[sender] = conversation_id


def conversation_for_sender(sender: str) -> int | None:
    """Return the open thread for this WhatsApp number, if this process has one."""
    return _senders.get(sender)


def shop_fact_line(session: Session) -> str:
    """The delivery facts saved for this shop."""
    row = session.get(ShopPolicy, DEMO_SHOP_ID)
    if row is None:
        return ""
    parts: list[str] = []
    if row.delivery_days is not None:
        parts.append(f"Delivery takes {row.delivery_days} days.")
    if row.delivery_price_tnd is not None:
        price = format(row.delivery_price_tnd, "f").rstrip("0").rstrip(".")
        parts.append(f"Delivery costs {price} TND.")
    return " ".join(parts)


def draft_social(session: Session, message: str, earlier: list, lead: object) -> ReplyDraft:
    """One model call for a hello. No catalog and no quiet window."""
    instructions = list(
        session.exec(select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)).all()
    )
    history = format_discussion(earlier)
    order_note = (
        f"product: {lead.product_name}\nsize: {lead.size}\n"
        f"phone: {lead.phone}\naddress: {lead.address}"
    ).strip()
    model = create_reply_model()
    facts = shop_fact_line(session)
    result = model.invoke(
        build_reply_messages([], message, instructions, history, order_note, {}, shop_line=facts)
    )
    if result["parsing_error"] is not None or result["parsed"] is None:
        raise HTTPException(
            status_code=502,
            detail="Reply drafting failed. No message was sent; please answer manually or retry.",
        )
    draft = validate_evidence(
        ReplyDraft.model_validate(result["parsed"]),
        [],
        instructions,
        lead.product_name,
        message,
        {},
        facts,
    )
    _remember_usage(session, _extract_usage(result["raw"]))
    return draft


def run_collected_draft(session: Session, conversation_id: int) -> None:
    """Draft one reply for the buyer lines that arrived after the last draft."""
    conversation, lead, turns = _load_discussion(session, conversation_id)
    burst: list[DiscussionTurn] = []
    for turn in reversed(turns):
        if turn.role != "buyer":
            break
        burst.append(turn)
    burst.reverse()
    if not burst:
        return
    message = "\n".join(turn.text.strip() for turn in burst if turn.text.strip())
    if not message:
        return
    step(conversation_id, "drafting", f"{len(burst)} buyer line(s)")
    prior = turns[: len(turns) - len(burst)]
    history = format_discussion(prior)
    order_note = (
        f"product: {lead.product_name}\nsize: {lead.size}\n"
        f"phone: {lead.phone}\naddress: {lead.address}"
    ).strip()
    products = list(session.exec(select(Product).where(Product.shop_id == DEMO_SHOP_ID)).all())
    facts_by_id = {
        product.id: list(
            session.exec(select(ProductFact).where(ProductFact.product_id == product.id)).all()
        )
        for product in products
        if product.id is not None
    }
    instructions = list(
        session.exec(select(ShopInstruction).where(ShopInstruction.shop_id == DEMO_SHOP_ID)).all()
    )
    try:
        safety_model = create_structured_model(SafetyFlag)
        route_model = create_structured_model(CatalogNeed)
        model = create_reply_model()
    except ModelNotConfigured:
        step(conversation_id, "failed", "GROQ_API_KEY is missing", ok=False)
        return

    started = time.perf_counter()
    facts = shop_fact_line(session)
    try:
        safety_result = safety_model.invoke(build_safety_messages(message))
        if safety_result["parsing_error"] is not None:
            raise ValueError("safety schema")
        tell_seller = SafetyFlag.model_validate(safety_result["parsed"]).tell_seller
        step(
            conversation_id,
            "safety",
            "Decision: hand to the seller" if tell_seller else "Decision: answer the buyer",
        )
        if tell_seller:
            draft = handoff_for_safety()
            _remember_usage(session, _extract_usage(safety_result["raw"]))
            session.add(SellerAlert(
                conversation_id=conversation_id,
                shop_id=DEMO_SHOP_ID,
                notice="Flagged. No reply was drafted.",
            ))
            session.add(DiscussionTurn(
                conversation_id=conversation_id,
                role="draft",
                text=draft.seller_question,
            ))
            session.commit()
            step(conversation_id, "saved", "No customer reply. Seller notice only.")
            return
        if asks_wholesale(message):
            step(conversation_id, "price", "Decision: wholesale or sale price. Ask the seller.")
            draft = handoff_for_wholesale()
            session.add(SellerAlert(
                conversation_id=conversation_id,
                shop_id=DEMO_SHOP_ID,
                notice="Wholesale price. No reply was drafted.",
            ))
            session.add(DiscussionTurn(
                conversation_id=conversation_id,
                role="draft",
                text=draft.seller_question,
            ))
            session.commit()
            return
        route_result = route_model.invoke(build_catalog_need_messages(message, history))
        if route_result["parsing_error"] is not None:
            raise ValueError("catalog schema")
        needs_catalog = CatalogNeed.model_validate(route_result["parsed"]).needs_catalog
        retrieved = products_for_question(products, needs_catalog)
        names = ", ".join(product.name for product in retrieved[:6]) or "none"
        decision = "load products" if needs_catalog else "skip products"
        step(conversation_id, "catalog", f"Decision: {decision}. Retrieved: {names[:60]}")
        result = model.invoke(
            build_reply_messages(
                retrieved, message, instructions, history, order_note, facts_by_id,
                shop_line=facts,
            )
        )
        if result["parsing_error"] is not None:
            raise ValueError("reply schema")
        first_draft = ReplyDraft.model_validate(result["parsed"])
        if needs_catalog_retry(first_draft) and products:
            step(conversation_id, "catalog", "Decision: retry with the full catalog")
            retrieved = products_for_question(products, True)
            result = model.invoke(
                build_reply_messages(
                    retrieved,
                    message,
                    instructions,
                    history,
                    order_note,
                    facts_by_id,
                    "Rewrite the draft. The product must match a record above. "
                    "If the color or model is not in those records, say ma famech. "
                    "Do not ask for the phone.",
                    shop_line=facts,
                )
            )
            if result["parsing_error"] is not None:
                raise ValueError("reply schema")
        draft = validate_evidence(
            ReplyDraft.model_validate(result["parsed"]),
            retrieved,
            instructions,
            lead.product_name,
            message,
            facts_by_id,
            facts,
        )
    except Exception as exc:
        step(conversation_id, "failed", f"{type(exc).__name__}: {exc}"[:500], ok=False)
        logger.exception(
            "Quiet-window model call failed type=%s status=%s",
            type(exc).__name__,
            getattr(exc, "status_code", None),
        )
        session.add(DiscussionTurn(
            conversation_id=conversation_id,
            role="draft",
            text="Reply drafting failed. Check the API window, then send the message again.",
        ))
        session.commit()
        return

    usage = _add_usage(_extract_usage(safety_result["raw"]), _extract_usage(route_result["raw"]))
    usage = _add_usage(usage, _extract_usage(result["raw"]))
    _remember_usage(session, usage)
    saved = (draft.reply_text or draft.seller_question).strip()
    if saved:
        session.add(DiscussionTurn(conversation_id=conversation_id, role="draft", text=saved))
    remember_order(
        lead, draft.order_product, draft.order_size, draft.order_phone, draft.order_address,
    )
    session.add(lead)
    session.commit()
    handoff = "needs the seller" if draft.needs_seller else "answers the buyer"
    preview = saved[:180] or "(empty)"
    step(
        conversation_id,
        "reply",
        f"Decision: {draft.customer_intent}, {handoff}. {preview}",
    )
    step(conversation_id, "saved", f"{usage.total_tokens} tokens")
    logger.info(
        "Quiet-window draft saved conversation=%s latency_ms=%s tokens=%s",
        conversation_id,
        round((time.perf_counter() - started) * 1000),
        usage.total_tokens,
    )


def waiting_draft() -> ReplyDraft:
    """Placeholder while later buyer lines can still join this burst."""
    return ReplyDraft(
        reply_text="",
        customer_intent="social_conversation",
        matched_product_ids=[],
        used_instruction_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )
