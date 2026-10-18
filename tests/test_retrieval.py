from shop_assistant.catalog import Product
from shop_assistant.retrieval import products_for_question


def test_product_question_sees_the_approved_catalog() -> None:
    products = [
        Product(id=2, sku="robe_bleue", shop_id="demo-shop", name="Robe bleue"),
        Product(id=6, sku="robe_azrar", shop_id="demo-shop", name="robe azrar"),
    ]

    assert products_for_question(products, True) == products


def test_conversation_does_not_open_the_catalog() -> None:
    product = Product(id=6, sku="robe_azrar", shop_id="demo-shop", name="robe azrar")

    assert products_for_question([product], False) == []
