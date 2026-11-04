"""Choose whether a reply may see the approved catalog.

The buyer can phrase a product, a color, or a greeting in too many ways to list.
A model call decides whether this message is about products. When it is, the
reply model reads the shop's approved products and picks the ones that fit.
When it is not, the catalog stays out of the prompt.
"""

from shop_assistant.models import Product


def products_for_question(products: list[Product], needs_catalog: bool) -> list[Product]:
    """Return the approved catalog only when the buyer is asking about products."""
    if not needs_catalog:
        return []
    return list(products)
