# Agent / system architecture

## Harness / evaluations (offline, never sends live messages)
- `evals/run.py`: synthetic cases through the same reply path.
- `evals/cases.jsonl`: seller-reviewed cases.
- Separate correctness and safety from fluency.

## Two model calls
1. **Instruction call** (`seller_instructions.py`): the seller writes a free-text note. A separate structured model call turns it into `rules`, `may_answer`, and `ask_seller`. The shop stores that result. This is the Chatbase-style “teach the assistant” step.
2. **Catalog decision** (`replies.py`): one short structured call reads the buyer message and sets `needs_catalog`. Greetings and other non-product talk skip the catalog. Product questions open it.
3. **Reply call** (`replies.py`): the reply model sees the saved discussion, the order details already collected, the approved products only when that decision is true, and the seller instructions when the shop has stored any. It writes one `ReplyDraft` in Tunisian Derja. A short follow-up such as a size stays on the same product. The order request is product, then size, then phone and address. The shop does not accept the order until the seller reviews it.
4. **Saved discussion** (`conversation.py`): each draft stores the buyer line, the draft, and the order details in SQLite. No tool call and no LangGraph. The same reply model reads that saved thread.

Ordinary text uses Groq `openai/gpt-oss-20b` for both calls. `GROQ_API_KEY` is required. There is no vision model.

## RAG path
- `catalog.py`: approved products.
- `retrieval.py`: returns the approved catalog when the model says the message is about products, and nothing when it is not. No color or greeting word list.
- `seller_instructions.py`: stored seller guidance.
- `replies.py`: prompt, structured generation, evidence check.
- `main.py`: HTTP, database, and the choice between an immediate handoff and a model call.

## When `needs_seller` is true
- The buyer shared a photo, voice message, video, or location. No model call. No customer draft.
- A shop fact is not in the retrieved products and not in the seller instructions.
- A seller instruction explicitly says to ask the seller.

## When `needs_seller` stays false
- Greetings and other social conversation. The model answers; validation clears any handoff.
- A shop answer cites retrieved product ids.
- A shop answer cites an active seller-instruction id. The seller already taught that fact, so the assistant does not ask again.

## Safety
- Cited product ids must be in the retrieved set.
- Cited instruction ids must be active for the shop.
- The assistant never sends a message by itself.
- Non-text shares are not downloaded, stored, or described.
