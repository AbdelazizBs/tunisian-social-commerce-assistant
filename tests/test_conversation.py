from shop_assistant.conversation import remember_order
from shop_assistant.models import OrderLead, SellerAlert


def test_abuse_alert_is_priority_and_flagged() -> None:
    alert = SellerAlert(conversation_id=1, shop_id="demo-shop", notice="Read their message.")

    assert alert.priority is True
    assert alert.flagged is True


def test_a_later_message_does_not_erase_the_saved_product() -> None:
    lead = OrderLead(conversation_id=1, shop_id="demo-shop", product_name="robe azrar")

    remember_order(lead, "", "S", "", "")

    assert lead.product_name == "robe azrar"
    assert lead.size == "S"
    assert lead.phone == ""
    assert lead.address == ""
