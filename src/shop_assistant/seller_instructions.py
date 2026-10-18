"""Seller notes normalized into rules the reply assistant can follow."""

from pydantic import BaseModel, Field
from sqlmodel import Field as SqlField
from sqlmodel import SQLModel


class InstructionContent(BaseModel):
    rules: list[str] = Field(description="How the assistant should speak and behave")
    may_answer: list[str] = Field(
        description=(
            "Facts and everyday situations the assistant should answer itself, "
            "without asking the seller"
        )
    )
    ask_seller: list[str] = Field(
        description="Cases that still need the seller. Ordinary greetings do not belong here."
    )


class ShopInstruction(SQLModel, table=True):
    id: int | None = SqlField(default=None, primary_key=True)
    shop_id: str = SqlField(index=True, max_length=80)
    source_text: str = SqlField(max_length=4000)
    content_json: str = SqlField(max_length=8000)

    def content(self) -> InstructionContent:
        return InstructionContent.model_validate_json(self.content_json)


INSTRUCTION_PROMPT = """You turn a shop seller's note into instructions for their sales assistant.
The assistant talks with buyers and should sound human, not like a form.
Split the note into three lists:
- rules: how to speak and behave
- may_answer: facts and everyday situations the assistant should handle itself
- ask_seller: only cases the seller still wants, or facts the seller did not provide
Put greetings, thanks, small talk, and anything the seller explained into may_answer.
Do not invent prices, stock, delivery fees, or policies the seller did not state.
Keep each item short.
"""


def build_instruction_messages(source_text: str) -> list[tuple[str, str]]:
    return [("system", INSTRUCTION_PROMPT), ("human", source_text)]
