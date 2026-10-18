import json
import os
from enum import StrEnum
from typing import Any, Literal

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from shop_assistant.catalog import Product
from shop_assistant.seller_instructions import ShopInstruction


class ReplyDraft(BaseModel):
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


class AttachmentKind(StrEnum):
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"


class CatalogNeed(BaseModel):
    needs_catalog: bool = Field(
        description=(
            "True only when the buyer is asking about a product, category, color, "
            "size, price, or stock. False for greetings, small talk, thanks, and "
            "questions that are not about products."
        )
    )


class ModelNotConfigured(Exception):
    pass


SYSTEM_PROMPT = """You are a Tunisian online shop seller writing a draft reply.
reply_text must be Tunisian Derja, the way people in Tunisia actually write to a shop.
This is required. A correct fact in the wrong dialect is a bad reply.

Script follows the buyer:
- Arabizi (Latin letters with 3 ع, 7 ح, 9 ق, 5 خ, 2 ء): Tunisian Arabizi only.
- Arabic letters: Tunisian Derja in Arabic letters, not formal Arabic.
- French: everyday Tunisian French, short, the way a shop in Tunisia writes.
- A mix: keep their mix. Do not answer in English unless they wrote in English.

Required Tunisian wording when the reply is Arabizi or Arabic:
- dress is "rouba", never "robes" or "robe" unless that exact product name is in the catalog.
- "there is / we have" is "fama" or "3andna".
- "what" is "chnouwa" or "chnowa". "which one" is "ama wahda" or "chnouwa el modèle".
- "you want" is "t7eb". "size" is "el taille". "price" is "el soum".
- greet with "marhba bik". Offer help with "fech najmou n3awnouk", or that meaning in their script.
- one or two short sentences. Sound like a person in a Tunis shop, not a translator.

Never write non-Tunisian Arabizi. Forbidden, even if the grammar looks Arabic:
- "Iwa, 3andna robes. T9dar t3tini l9a3da?"
- "l9a3da", "t9dar t3tini", "iwa" used as a sentence starter, English "robes".
Say instead, when several dresses fit: "Fama rouba. Chnouwa el modèle elli t7eb?"
Do not copy that sentence every time. Change it to the buyer's script and to the real question.

Do not use Egyptian, Moroccan, Algerian, or Gulf wording (izzayek, 3ayez, wach, bzzaf, shlon).
Do not use formal Arabic (هل, لديكم, فضلا, يمكنني).
Preserve seller product names exactly. Never invent attributes, mention
internal IDs/SKUs, or dump a product list.

Classify the meaning of the whole message.
A greeting is polite, not confusion. "aslema", "asslema", "bonjour", "hello",
"salut", and "salam" mean hello. Reply warmly and offer help, for example
"Marhba bik, fech najmou n3awnouk?". Never answer a greeting with "Mafhemtech".
"labes", "labes ?", and "labes ? ds" mean "how are you?", not hello. Answer the
question first, for example "Labes, elhamdullah. W enti?". Do not answer "labes"
with "Marhba bik".
"hamdoullah" answers "w enti?". It is not a new hello. Reply "Behi." Do not
repeat "Marhba bik".
Use "Mafhemtech. Chnouwa t7eb?" only for random letters such as "nbfjkdsh" or
laughter such as "hhh", when no word can be read.
Thanks, goodbyes, and these greetings are customer_intent="social_conversation".
Social conversation needs no catalog evidence, uses no instruction ids, and never
requires a seller. Never leave reply_text empty for this. If a greeting is mixed
with a product or shop question, use customer_intent="shop_question".

Product records are included only when the buyer is asking about products. Read
those records and decide which one or which several they mean, including from
Tunisian Arabic, Arabizi, French, or a mix. Do not expect a fixed word list.
If several available products fit, answer briefly and ask which one they mean.
Do not escalate that clarification. Seller instructions are included whenever the
shop has stored any. If a shop question is covered by an instruction, cite its id
in used_instruction_ids, answer the buyer, and set needs_seller=false. If the
needed fact is in neither source, set needs_seller=true, leave reply_text empty,
and put one concise question in seller_question. Use an empty seller_question
when the seller is not needed. Never guess price, stock, delivery, or policy.

For a broad availability question, answer briefly in Tunisian and ask one
short follow-up when needed. Do not invent a count from the number of retrieved records.

The goal of a product conversation is one order request. Read the saved order
details and the whole discussion. Trust a detail that is already saved.
Collect only: product, size, phone number, address.
A short message such as "S" or "M" is a size you can sell. Save it and ask the next missing detail.
"behy", "behi", "bahi", and "باهي" mean the buyer accepts what you just said.
If you just said the requested size is not available, do not ask "Chnouwa el taille?" again
and do not save that size. Offer more help in the same script the buyer uses:
Arabizi "Najmouch n3awnouk f haja okhra?", Arabic letters "نجمو نعاونوك في حاجة أخرى؟",
French "Je peux t'aider avec autre chose ?".
"ok", "yes", "ey", "أي", "إي", or "نعم" confirms a detail you can save. Then move on.
Do not ask that question again.

If you already asked which model, the buyer's next product names are the answer.
"w" means and, so "robe d'été w azrar" means both models, not a new search.
Save both in order_product. Do not say "fama" again and do not ask
"Chnouwa el modèle elli t7eb?" a second time. The next missing detail is the size,
so reply_text is only "Chnouwa el taille?".
Forbidden: "Fama rouba d'été w rouba azrar. Chnouwa el modèle elli t7eb?"

reply_text asks for one missing detail only. Do not greet again, do not repeat
the product, the size, or any detail already saved, and do not recap the order
until phone and address are both known.
Forbidden shape: "marhba bik, t7eb rouba d'été? El taille S. 3tini nummar telfouni w l'adresse."
After the size is known, the next reply is only the phone request.
When the phone is known, the next reply is only the address request.

Ask for the phone and the address in Arabic letters, Tunisian Derja, not Arabizi
and not French. Use "شنوّة نومرو تيليفونك؟" for the phone and "شنوّة العنوان؟" for
the address. Never write "nummar", "telfouni", "numéro", or "numero".
When product, size, phone, and address are all saved, then one short Arabic
summary is allowed, and ask "صحيح؟". Never say the shop already accepted the order.
Copy known details into order_product, order_size, order_phone, and order_address.
Use an empty string only for a detail that is still missing. Never clear a saved detail.
"""


def create_structured_model(schema: type[BaseModel], *, api_key: str | None = None) -> Any:
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
        schema,
        method="json_schema",
        strict=True,
        include_raw=True,
    )


def create_reply_model(*, api_key: str | None = None) -> Any:
    return create_structured_model(ReplyDraft, api_key=api_key)


def handoff_for_attachment(kind: AttachmentKind) -> ReplyDraft:
    shared = {
        AttachmentKind.IMAGE: "a photo",
        AttachmentKind.VOICE: "a voice message",
        AttachmentKind.VIDEO: "a video",
        AttachmentKind.LOCATION: "a location",
    }[kind]
    return ReplyDraft(
        reply_text="",
        customer_intent="shop_question",
        matched_product_ids=[],
        used_instruction_ids=[],
        needs_seller=True,
        seller_question=f"The buyer shared {shared}. What should I tell them?",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )


CATALOG_NEED_PROMPT = """Decide if the sales assistant must read the product catalog.
Read the earlier discussion and the new message together.
Set needs_catalog to true when the buyer asks about a product, a category, a color,
a size, a price, or stock, and also when the new message only fills in a detail
for a product already discussed, such as "S", "M", or "L".
Set needs_catalog to false for greetings, wellbeing, thanks, and goodbyes that
do not continue a product order.
Do not answer the buyer.
"""


def build_catalog_need_messages(
    buyer_message: str,
    history: str = "",
) -> list[tuple[str, str]]:
    earlier = f"Earlier discussion:\n{history}\n\n" if history else ""
    return [("system", CATALOG_NEED_PROMPT), ("human", f"{earlier}New message:\n{buyer_message}")]


def build_reply_messages(
    retrieved_products: list[Product],
    buyer_message: str,
    instructions: list[ShopInstruction] | None = None,
    history: str = "",
    order_note: str = "",
) -> list[tuple[str, str]]:
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
            for product in retrieved_products
        ],
        ensure_ascii=False,
    )
    instruction_json = json.dumps(
        [
            {"id": item.id, **item.content().model_dump()}
            for item in (instructions or [])
        ],
        ensure_ascii=False,
    )
    return [
        (
            "system",
            f"{SYSTEM_PROMPT}\n"
            "Approved sources: product records for this turn, and the shop's seller instructions.\n"
            f"Product records: {catalog_json}\n"
            f"Seller instructions: {instruction_json}",
        ),
        (
            "human",
            "Write the draft in Tunisian Derja, in the buyer's script. "
            "Arabizi stays Tunisian Arabizi. Arabic letters stay Tunisian Derja. "
            "French stays everyday Tunisian French. "
            "Do not answer in English, formal Arabic, or another country's dialect.\n\n"
            f"{'Earlier discussion:\n' + history + '\n\n' if history else ''}"
            f"{'Order details already saved:\n' + order_note + '\n\n' if order_note else ''}"
            f"New buyer message:\n{buyer_message}",
        ),
    ]


def validate_evidence(
    draft: ReplyDraft,
    retrieved_products: list[Product],
    instructions: list[ShopInstruction] | None = None,
    known_product: str = "",
    buyer_message: str = "",
) -> ReplyDraft:
    allowed_ids = {product.id for product in retrieved_products if product.id is not None}
    if any(product_id not in allowed_ids for product_id in draft.matched_product_ids):
        raise ValueError("The model cited a product outside the retrieved approved records")

    allowed_instruction_ids = {
        item.id for item in (instructions or []) if item.id is not None
    }
    if any(item_id not in allowed_instruction_ids for item_id in draft.used_instruction_ids):
        raise ValueError("The model cited an instruction that is not active")

    if _is_wellbeing(buyer_message) and _reply_missed_wellbeing(draft.reply_text):
        draft = draft.model_copy(
            update={
                "reply_text": "Labes, elhamdullah. W enti?",
                "customer_intent": "social_conversation",
                "needs_seller": False,
                "seller_question": "",
                "matched_product_ids": [],
                "used_instruction_ids": [],
            }
        )
    elif _accepts_and_stops(buyer_message) and _still_asking_size(draft.reply_text):
        draft = draft.model_copy(
            update={
                "reply_text": _more_help(buyer_message),
                "customer_intent": "social_conversation",
                "needs_seller": False,
                "seller_question": "",
                "order_size": "",
                "matched_product_ids": [],
                "used_instruction_ids": [],
            }
        )
    elif _is_hamdoullah(buyer_message) and "marhba" in draft.reply_text.casefold():
        draft = draft.model_copy(
            update={
                "reply_text": "Behi.",
                "customer_intent": "social_conversation",
                "needs_seller": False,
                "seller_question": "",
                "matched_product_ids": [],
                "used_instruction_ids": [],
            }
        )
    elif _is_greeting(buyer_message) and _reply_missed_the_greeting(draft.reply_text):
        draft = draft.model_copy(
            update={
                "reply_text": "Marhba bik, fech najmou n3awnouk?",
                "customer_intent": "social_conversation",
                "needs_seller": False,
                "seller_question": "",
                "matched_product_ids": [],
                "used_instruction_ids": [],
            }
        )

    if draft.customer_intent == "social_conversation":
        if draft.matched_product_ids:
            raise ValueError("A social reply must not cite product records")
        if not draft.reply_text.strip():
            raise ValueError("The model did not generate a social reply")
        return draft.model_copy(
            update={"needs_seller": False, "seller_question": "", "used_instruction_ids": []}
        )

    grounded = bool(draft.matched_product_ids or draft.used_instruction_ids)
    remembered = draft.order_product.strip() or known_product.strip()
    if not draft.needs_seller and not grounded:
        if remembered:
            if not draft.order_product.strip():
                return draft.model_copy(update={"order_product": known_product})
            return draft
        if not _states_shop_fact(draft.reply_text):
            reply = draft.reply_text.strip() or "Mafhemtech. Chnouwa t7eb?"
            return draft.model_copy(
                update={
                    "reply_text": reply,
                    "customer_intent": "social_conversation",
                    "needs_seller": False,
                    "seller_question": "",
                    "matched_product_ids": [],
                    "used_instruction_ids": [],
                }
            )
        return ReplyDraft(
            reply_text="",
            customer_intent="shop_question",
            matched_product_ids=[],
            used_instruction_ids=[],
            needs_seller=True,
            seller_question=(
                "I could not verify this from the approved product information "
                "or your instructions. What should I tell the buyer?"
            ),
            order_product=draft.order_product,
            order_size=draft.order_size,
            order_phone=draft.order_phone,
            order_address=draft.order_address,
        )
    return draft


def _is_greeting(buyer_message: str) -> bool:
    words = {part.strip("؟?!.,:؛") for part in buyer_message.casefold().split()}
    greetings = {
        "aslema", "asslema", "asllema", "bonjour", "hello", "salut", "hi", "salam", "ahla",
    }
    return bool(words & greetings) and "labes" not in words


def _is_wellbeing(buyer_message: str) -> bool:
    words = {part.strip("؟?!.,:؛") for part in buyer_message.casefold().split()}
    return bool(words & {"labes", "labess", "labes?"})


def _accepts_and_stops(buyer_message: str) -> bool:
    words = {part.strip("؟?!.,:؛") for part in buyer_message.casefold().split()}
    return bool(words & {"behy", "behi", "bahi", "باهي"})


def _is_hamdoullah(buyer_message: str) -> bool:
    words = {part.strip("؟?!.,:؛") for part in buyer_message.casefold().split()}
    return bool(words & {"hamdoullah", "hamdoulah", "elhamdullah", "الحمد لله"})


def _still_asking_size(reply_text: str) -> bool:
    folded = reply_text.casefold()
    return "taille" in folded or "تاي" in reply_text


def _more_help(buyer_message: str) -> str:
    if any("\u0600" <= char <= "\u06ff" for char in buyer_message):
        return "نجمو نعاونوك في حاجة أخرى؟"
    if any(word in buyer_message.casefold() for word in ("bonjour", "salut", "merci")):
        return "Je peux t'aider avec autre chose ?"
    return "Najmouch n3awnouk f haja okhra?"


def _reply_missed_wellbeing(reply_text: str) -> bool:
    folded = reply_text.casefold()
    return not folded.strip() or "marhba" in folded or "mafhemtech" in folded


def _reply_missed_the_greeting(reply_text: str) -> bool:
    folded = reply_text.casefold()
    return not folded.strip() or "mafhemtech" in folded


def _states_shop_fact(reply_text: str) -> bool:
    """True when an uncited reply states a price or availability the seller must check."""
    folded = reply_text.casefold()
    markers = ("tnd", "dt", "dinar", "disponible", "available", "mawjoud", "موجود", "soum", "سعر")
    return any(marker in folded for marker in markers)
