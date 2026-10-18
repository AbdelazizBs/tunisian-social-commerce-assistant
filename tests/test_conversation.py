from shop_assistant.conversation import OrderLead, remember_order


def test_a_later_message_does_not_erase_the_saved_product() -> None:
    lead = OrderLead(conversation_id=1, shop_id="demo-shop", product_name="robe azrar")

    remember_order(lead, "", "S", "", "")

    assert lead.product_name == "robe azrar"
    assert lead.size == "S"
    assert lead.phone == ""
    assert lead.address == ""
