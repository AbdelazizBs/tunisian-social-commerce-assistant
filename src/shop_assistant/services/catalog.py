"""Turn a product description into labeled facts. The records live in models.py."""

STRUCTURE_PROMPT = """Read a shop product description and turn it into short labeled facts.
The product can be anything: clothes, food, electronics, or another kind.
Use only words written in the name or description. Do not invent a size, color, price, or material.
Each fact has a short label and one clear value, such as "color: noir" or "size: S".
Do not write "unknown", "maybe", or "not specified".
If the description has no factual details, return an empty facts list.
"""


def build_structure_messages(name: str, description: str) -> list[tuple[str, str]]:
    """Ask the model for facts that are written in the name or description."""
    return [
        ("system", STRUCTURE_PROMPT),
        ("human", f"Name: {name}\nDescription: {description}"),
    ]

