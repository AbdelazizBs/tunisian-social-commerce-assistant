import json

import pytest

from shop_assistant.models import (
    AttachmentKind,
    Availability,
    InstructionContent,
    Product,
    ReplyDraft,
    ShopInstruction,
)
from shop_assistant.replies import (
    asks_wholesale,
    build_catalog_need_messages,
    build_reply_messages,
    build_safety_messages,
    handoff_for_attachment,
    handoff_for_safety,
    is_social_only,
    validate_evidence,
)
from shop_assistant.seller_instructions import build_instruction_messages


def test_wholesale_words_go_to_the_seller() -> None:
    assert asks_wholesale("3andek beljomla?")
    assert asks_wholesale("prix gros pour 20 pieces")
    assert asks_wholesale("بالجملة قداه")
    assert asks_wholesale("soldes ken fama")
    assert not asks_wholesale("qadeh el total mta3 zouz robe + livraison")


def test_hey_and_slm_take_the_same_social_path() -> None:
    assert is_social_only("hey")
    assert is_social_only("slm")
    assert is_social_only("salut")
    assert not is_social_only("slm taille M")


def test_uncited_answer_is_converted_to_seller_handoff() -> None:
    draft = ReplyDraft(
        reply_text="This is available.",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [])

    assert result.needs_seller is True
    assert result.reply_text == ""
    assert result.seller_question is not None


def test_greeting_is_welcomed_even_if_the_model_says_it_does_not_understand() -> None:
    draft = ReplyDraft(
        reply_text="Mafhemtech. Chnouwa t7eb?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="aslema")

    assert result.needs_seller is False
    assert result.reply_text == "Marhba bik, fech najmou n3awnouk?"


def test_labes_is_answered_as_how_are_you() -> None:
    draft = ReplyDraft(
        reply_text="marhba bik, fech najmou n3awnouk?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="labes ? ds")

    assert result.reply_text == "Labes, elhamdullah. W enti?"
    assert "marhba" not in result.reply_text.casefold()


def test_behy_after_a_missing_size_offers_more_help() -> None:
    draft = ReplyDraft(
        reply_text="Chnouwa el taille?",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="robe été",
        order_size="L",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="behy")

    assert result.reply_text == "Najmouch n3awnouk f haja okhra?"
    assert result.order_size == ""
    assert "taille" not in result.reply_text.casefold()


def test_order_request_asks_for_the_missing_product() -> None:
    draft = ReplyDraft(
        reply_text="Najmouch n3awnouk f haja okhra?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="behy 3adili command")

    assert result.reply_text == "Chnouwa el produit elli t7eb?"
    assert "haja okhra" not in result.reply_text.casefold()


def test_order_request_asks_for_phone_and_address_when_the_product_is_known() -> None:
    draft = ReplyDraft(
        reply_text="Najmouch n3awnouk f haja okhra?",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="robe été",
        order_size="S",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="3adili commande")

    assert "نومرو" in result.reply_text
    assert "العنوان" in result.reply_text


def test_hamdoullah_does_not_restart_the_greeting() -> None:
    draft = ReplyDraft(
        reply_text="Marhba bik, fech najmou n3awnouk?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], buyer_message="hamdoullah")

    assert result.reply_text == "Behi."


def test_unreadable_message_asks_the_buyer_not_the_seller() -> None:
    draft = ReplyDraft(
        reply_text="",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [])

    assert result.needs_seller is False
    assert result.seller_question == ""
    assert result.reply_text == "Mafhemtech. Chnouwa t7eb?"


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
        customer_intent="shop_question",
        matched_product_ids=[999],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    with pytest.raises(ValueError, match="outside the retrieved approved records"):
        validate_evidence(draft, [product])






def test_greeting_without_catalog_does_not_become_seller_handoff() -> None:
    model_draft = ReplyDraft(
        reply_text="Hamdoullah labes, wenti?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=True,
        seller_question="What product are you asking about?",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(model_draft, [])

    assert result.reply_text == "Hamdoullah labes, wenti?"
    assert result.needs_seller is False
    assert result.seller_question == ""


def test_tunisian_social_check_in_is_not_a_seller_handoff() -> None:
    draft = ReplyDraft(
        reply_text="Labes, hamdoullah. W enti?",
        customer_intent="social_conversation",
        matched_product_ids=[],
        needs_seller=True,
        seller_question="What is the answer?",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [])

    assert result.reply_text
    assert result.needs_seller is False
    assert result.seller_question == ""
def test_catalog_decision_reads_the_buyer_without_a_word_list() -> None:
    system_message, buyer = build_catalog_need_messages("fama rouba 7amra ?")

    assert "needs_catalog" in system_message[1]
    assert "greetings" in system_message[1]
    assert "fama rouba 7amra ?" in buyer[1]
    assert "7amra" not in system_message[1]


def test_size_follow_up_keeps_the_product_already_discussed() -> None:
    history = "Buyer: fama rwob azrar?\nAssistant draft: Chnouwa el taille?"
    _, buyer = build_catalog_need_messages("S", history)
    reply_buyer = build_reply_messages(
        [], "S", history=history, order_note="product: robe azrar"
    )[1][1]

    assert "rwob azrar" in buyer[1]
    assert "S" in buyer[1]
    assert "robe azrar" in reply_buyer
    assert "S" in reply_buyer


def test_size_missing_from_approved_facts_does_not_ask_for_the_phone() -> None:
    product = Product(
        id=3,
        sku="robe_ete",
        shop_id="demo-shop",
        name="robe d'été",
        availability=Availability.AVAILABLE,
    )
    fact = type("Fact", (), {"label": "size", "value": "S"})()
    draft = ReplyDraft(
        reply_text="شنوّة نومرو تيليفونك؟",
        customer_intent="shop_question",
        matched_product_ids=[3],
        needs_seller=False,
        seller_question="",
        order_product="robe d'été",
        order_size="L",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [product], facts_by_id={3: [fact]})

    assert result.order_size == ""
    assert "taille L" in result.reply_text
    assert "S" in result.reply_text
    assert "نومرو" not in result.reply_text


def test_prompt_answers_only_from_shop_sources() -> None:
    system_message = build_reply_messages([], "aslema")[0][1]

    assert "approved facts" in system_message
    assert "do not guess" in system_message.casefold()
    assert "clarifying question" in system_message


def test_prompt_reads_short_tunisian_spellings() -> None:
    system_message = build_reply_messages([], "b9adech ?")[0][1]

    assert '"dete" is "d\'été"' in system_message
    assert "b9adech" in system_message
    assert "approved_facts" in system_message


def test_phone_question_without_a_product_is_rejected() -> None:
    draft = ReplyDraft(
        reply_text="شنوّة نومرو تيليفونك؟",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="robe dete noir",
        order_size="S",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [])

    assert "نومرو" not in result.reply_text
    assert result.order_product == ""
    assert "ma famech" in result.reply_text.casefold()


def test_prompt_asks_phone_and_address_together() -> None:
    system_message = build_reply_messages([], "robe dete noir T S")[0][1]

    assert "same reply" in system_message
    assert "robe dete noir T S" in system_message
    assert "only the phone request" not in system_message


def test_prompt_asks_only_the_missing_phone_in_arabic() -> None:
    system_message = build_reply_messages([], "S")[0][1]

    assert "same reply" in system_message
    assert "شنوّة نومرو تيليفونك؟" in system_message
    assert "شنوّة العنوان؟" in system_message
    assert "wa9teh touselni" in system_message
    assert "ma3lich" in system_message
    assert "T9sed robe d'été, taille L?" in system_message
    assert "nummar" in system_message
    assert "telfouni" in system_message
    assert "Chnouwa el modèle elli t7eb?" in system_message
    assert "Chnouwa el taille?" in system_message


def test_saved_product_lets_a_size_answer_continue() -> None:
    draft = ReplyDraft(
        reply_text="Chnouwa el numéro w el adresse?",
        customer_intent="shop_question",
        matched_product_ids=[],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="S",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], known_product="robe azrar")

    assert result.needs_seller is False
    assert result.order_product == "robe azrar"
    assert result.order_size == "S"
    assert result.reply_text.startswith("Chnouwa")


def test_reply_prompt_lets_the_model_read_product_records() -> None:
    product = Product(
        id=6,
        sku="robe_azrar",
        shop_id="demo-shop",
        name="robe azrar",
        description="color: rouge",
        availability=Availability.AVAILABLE,
    )

    system_message = build_reply_messages([product], "fama rouba 7amra ?")[0][1]

    assert "robe azrar" in system_message
    assert "Do not expect a fixed word list" in system_message
    assert "7amra' means red" not in system_message


def test_illegal_message_goes_to_the_seller_without_a_customer_draft() -> None:
    draft = handoff_for_safety()

    assert draft.needs_seller is True
    assert draft.reply_text == ""
    assert draft.seller_question == ""


def test_safety_check_does_not_treat_a_shop_question_as_illegal() -> None:
    system_message, buyer = build_safety_messages("wa9teh touselni ?")

    assert "tell_seller" in system_message[1]
    assert "insult" in system_message[1]
    assert "word list" in system_message[1]
    assert buyer[1] == "wa9teh touselni ?"


def test_non_text_shares_go_to_the_seller() -> None:
    expected = {
        AttachmentKind.IMAGE: "The buyer shared a photo. What should I tell them?",
        AttachmentKind.VOICE: "The buyer shared a voice message. What should I tell them?",
        AttachmentKind.VIDEO: "The buyer shared a video. What should I tell them?",
        AttachmentKind.LOCATION: "The buyer shared a location. What should I tell them?",
    }

    for kind, question in expected.items():
        draft = handoff_for_attachment(kind)
        assert draft.needs_seller is True
        assert draft.reply_text == ""
        assert draft.seller_question == question
        assert draft.matched_product_ids == []
        assert draft.used_instruction_ids == []


def test_answer_grounded_in_seller_instruction_does_not_need_seller() -> None:
    instruction = _delivery_instruction()
    draft = ReplyDraft(
        reply_text="Livraison Tunis 7 TND.",
        customer_intent="shop_question",
        matched_product_ids=[],
        used_instruction_ids=[4],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    result = validate_evidence(draft, [], [instruction])

    assert result.needs_seller is False
    assert result.reply_text == "Livraison Tunis 7 TND."
    assert result.seller_question == ""


def test_unknown_instruction_citation_is_rejected() -> None:
    draft = ReplyDraft(
        reply_text="Livraison 7 TND.",
        customer_intent="shop_question",
        matched_product_ids=[],
        used_instruction_ids=[9],
        needs_seller=False,
        seller_question="",
        order_product="",
        order_size="",
        order_phone="",
        order_address="",
    )

    with pytest.raises(ValueError, match="instruction that is not active"):
        validate_evidence(draft, [], [])


def test_reply_schema_omits_defaults_groq_strict_rejects() -> None:
    from langchain_core.utils.function_calling import convert_to_json_schema

    schema = convert_to_json_schema(ReplyDraft, strict=True)

    assert "default" not in json.dumps(schema)
    assert set(schema["required"]) == set(schema["properties"])


def test_reply_prompt_keeps_the_buyer_language() -> None:
    system_message, buyer = build_reply_messages([], "labes alik ?")

    assert "Tunisian Derja" in system_message[1]
    assert "l9a3da" in system_message[1]
    assert "Tunisian Derja" in buyer[1]
    assert "labes alik ?" in buyer[1]


def test_seller_instruction_is_available_to_the_reply_model() -> None:
    system_message = build_reply_messages([], "livraison?", [_delivery_instruction()])[0][1]

    assert "Delivery to Tunis is 7 TND" in system_message
    assert '"id": 4' in system_message


def test_structure_prompt_uses_only_the_description() -> None:
    from shop_assistant.catalog import build_structure_messages

    messages = build_structure_messages("Robe d'été", "Noire, taille S")

    assert "Do not invent" in messages[0][1]
    assert "Noire, taille S" in messages[1][1]


def test_instruction_update_shows_what_the_new_note_replaced() -> None:
    from shop_assistant.seller_instructions import instruction_diff

    removed, added = instruction_diff(
        ["Delivery takes 2 days"],
        ["Delivery takes 3 days", "Be warm"],
    )

    assert removed == ["Delivery takes 2 days"]
    assert added == ["Be warm", "Delivery takes 3 days"]


def test_instruction_model_receives_the_old_and_new_note() -> None:
    note = "Delivery takes 3 days."

    messages = build_instruction_messages(note, ["Delivery takes 2 days"])

    assert messages[0][0] == "system"
    assert "drop the old one" in messages[0][1]
    assert "Delivery takes 2 days" in messages[1][1]
    assert note in messages[1][1]


def _delivery_instruction() -> ShopInstruction:
    return ShopInstruction(
        id=4,
        shop_id="demo-shop",
        source_text="Livraison Tunis 7 TND",
        content_json=InstructionContent(
            rules=["Answer delivery questions you were taught"],
            may_answer=["Delivery to Tunis is 7 TND"],
            ask_seller=["Embroidery price"],
        ).model_dump_json(),
    )


