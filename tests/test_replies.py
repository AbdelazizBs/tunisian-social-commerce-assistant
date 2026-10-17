import pytest

from shop_assistant.catalog import Availability, Product
from shop_assistant.replies import ReplyDraft, validate_evidence


def test_uncited_answer_is_converted_to_seller_handoff() -> None:
    draft = ReplyDraft(
        reply_text="This is available.",
        matched_product_ids=[],
        needs_seller=False,
        seller_question=None,
    )

    result = validate_evidence(draft, [])

    assert result.needs_seller is True
    assert result.reply_text == ""
    assert result.seller_question is not None


def test_unknown_product_citation_is_rejected() -> None:
    product = Product(
        id=7,
        sku="robe",
        shop_id="demo-shop",
        name="Robe bleue",
        availability=Availability.AVAILABLE,
    )
    draft = ReplyDraft(
        reply_text="C'est 65 TND.",
        matched_product_ids=[999],
        needs_seller=False,
        seller_question=None,
    )

    with pytest.raises(ValueError, match="outside the approved catalog"):
        validate_evidence(draft, [product])
