"""Turn a seller note into a skill. The records live in models.py."""

from shop_assistant.models import InstructionContent

INSTRUCTION_PROMPT = """You update the shop's approved instructions from the seller's new note.
The assistant may answer only from these lists. It has no other facts.
Split the result into three lists:
- rules: how to speak and behave
- may_answer: facts the assistant may tell buyers
- ask_seller: only what the seller still wants asked
Keep every current fact the new note does not change.
If the new note changes a fact, drop the old one.
Never keep two different numbers for the same fact.
Copy the seller's numbers exactly. Do not invent a day count, price, or policy.
Keep each item short.
"""


def build_instruction_messages(
    source_text: str,
    previous_facts: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Ask the model to merge the new note into the current skill."""
    current = "\n".join(f"- {fact}" for fact in (previous_facts or [])) or "None yet."
    return [
        ("system", INSTRUCTION_PROMPT),
        (
            "human",
            f"Current approved facts:\n{current}\n\nNew seller note:\n{source_text}",
        ),
    ]


def content_from_note(text: str) -> InstructionContent:
    """Split a seller skill without a model call.

    A long note is already the instruction. Delivery prices and example replies
    are facts the assistant may say. Escalations stay questions for the seller.
    """
    rules: list[str] = []
    may_answer: list[str] = []
    ask_seller: list[str] = []
    section = "rules"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = line.upper()
        rule_heading = ("LANGUAGE", "TONE", "STYLE", "PRIVACY", "FLOW", "NEGOTIABLE")
        if any(word in heading for word in rule_heading):
            section = "rules"
        elif any(word in heading for word in ("DELIVERY", "PRICE", "SALES", "EXAMPLE")):
            section = "may"
        elif any(word in heading for word in ("COMPLAINT", "TRUST", "HUMAN", "ESCALAT")):
            section = "ask"
        item = line[:400]
        if section == "may":
            may_answer.append(item)
        elif section == "ask":
            ask_seller.append(item)
        else:
            rules.append(item)
    if not rules and not may_answer:
        rules = [line[:400] for line in instruction_lines(text)[:30]]
    return InstructionContent(
        rules=rules[:30],
        may_answer=may_answer[:30],
        ask_seller=ask_seller[:30],
    )


def instruction_lines(text: str) -> list[str]:
    """Keep each non-empty line of a seller note."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def instruction_diff(previous: list[str], updated: list[str]) -> tuple[list[str], list[str]]:
    """Return lines the seller removed, then lines the seller added."""
    old = set(previous)
    new = set(updated)
    return sorted(old - new), sorted(new - old)