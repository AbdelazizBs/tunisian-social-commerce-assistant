# Product delivery plan: Tunisian shop assistant

**Basis:** Product specification v0.1 and decisions confirmed by Aziz. The application uses a Python modular monolith: FastAPI, SQLModel (SQLite locally; PostgreSQL when hosted), LangChain `ChatGroq` with strict structured output, and Groq `openai/gpt-oss-20b` for synthetic-data demos. No custom agent graph until live handoffs require durable pause/resume. See [technical architecture](technical-architecture.md). This is a product roadmap; implementation starts with a local manual-reply copilot.

## Product in one minute

One shop assistant helps a buyer discover a product, answer approved questions, and complete an order request. It uses the shop's approved catalog and policies. When it lacks an answer, it tells the buyer it will check and asks the seller for the answer or an approved source. The seller stays responsible for accepting the order and fulfilling it.

## Agent design

Do not start with a swarm of independent agents. Build one conversational assistant with clear capabilities and a single source of truth:

- **Product knowledge:** search approved product cards, variants, prices, seller policies, availability, delivery areas, and fees.
- **Conversation:** understand the buyer's intent and language; match a clear product; answer safely or ask one short clarifying question.
- **Order capture:** collect required fields one at a time, summarize them, and create a pending seller-review request only after the buyer confirms.
- **Seller handoff:** pause that conversation, show what is unknown and the relevant context, then use the seller's response only after approval.

The product-card importer is a seller-facing tool, not another autonomous customer-facing agent. It turns a post and its images into draft facts; the seller approves them before use.

## How replies feel natural

- Match the buyer's Tunisian Arabic, Arabic, French, code-switching, or Arabizi when the assistant can do so reliably.
- Keep replies short, locally phrased, and consistent with the shop's approved tone. Avoid generic chatbot greetings and repeated explanations.
- Remember details already provided. Ask only for the next missing order detail, not the full form again.
- Use the channel's media and structure when useful, such as showing clear product choices, rather than describing everything in a long paragraph.
- Be honest if asked whether it is automated. Natural writing is the goal; impersonating a human is not.
- When uncertain, say it will check and hand off. A natural-sounding wrong answer is worse than a quick, honest pause.

## Model and cost plan

**Demo:** Groq with `openai/gpt-oss-20b` is a candidate for synthetic-data demos, not a production dependency. Groq's rate-limit page lists 30 requests/minute, 1,000/day, 8,000 tokens/minute, and 200,000/day for this model, but describes those as base Developer-plan limits. Verify free-tier availability, live organization limits, and current data terms in the account before the demo. Do not use real buyer messages, phone numbers, addresses, or seller secrets.

**Production:** Choose after a small, seller-reviewed evaluation set. Compare Tunisian Arabic, Arabizi, French, mixed-language replies, product grounding, order-field extraction, safe handoff, p95 latency, cost, availability, and provider data terms. Start with one suitable paid model. Add a cheaper model for routine text or a separate media model only if measured cost or quality justifies it.

**Per-shop economics:** Track text, image, and audio usage separately. Estimate `shop cost = fixed hosting/support allocation + text-model cost + image cost + audio/transcription cost + channel/partner fees`. Set a base subscription with an included usage allowance and measured overage; keep Meta template charges separate when the seller pays Meta directly. Use pilot cost as a margin floor, not as the only price input. No unlimited plan until sustained high-volume unit economics are proven.

Set per-shop usage and spend alerts and a hard budget limit. Near the limit, pause automated replies safely and notify the owner rather than silently switching to a weaker model or sending unreviewed answers.

Current demo candidate sources, checked 2026-10-17:

- [Groq free-tier rate limits](https://console.groq.com/docs/rate-limits)
- [Groq model availability and current prices](https://console.groq.com/docs/models)
- [Groq data retention and Zero Data Retention](https://console.groq.com/docs/your-data)
- [Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement)
- [Gemini API unpaid-service data terms](https://ai.google.dev/gemini-api/terms)

## Delivery stages

```mermaid
flowchart LR
    A[Validate seller workflow and Meta gates] --> B[Approved product cards and shop policies]
    B --> C[Manual reply copilot pilot]
    C --> D[Order capture and seller handoff]
    D --> E[Official WhatsApp integration]
    E --> F[Official Messenger integration]
    F --> G[Measure reliability, quality, and unit cost]
```

The order of WhatsApp and Messenger after the manual pilot is a recommendation, not a proven channel-priority decision. Confirm it with pilot sellers' message volume and actual Meta account eligibility.

### Stage 0: prove the path before building automation

**Work:** Interview target apparel sellers about message volume, repeated questions, post formats, current catalog/stock habits, and their response workflow. Test Meta business verification and the API access path with developer-owned assets. Start App Review preparation while building only what is needed to demonstrate the proposed use case.

**Gate:** Sellers confirm the repeated-message and order-capture pain; at least one pilot shop can participate; the product owner knows whether first-party Meta verification is feasible. If Meta access is delayed, continue only with the manual copilot, not unofficial inbox automation.

### Stage 1: make shop knowledge usable

**Work:** Build seller setup for the initial apparel use case, policy entry, and structured product cards. Let a seller paste post text and upload images; suggest separate products for clear images; leave unknown facts blank; support splitting/editing ambiguous posts; require approval before an agent can answer from a card. Keep available/sold-out/unknown availability, not unverified exact stock counts.

**Gate:** A seller can add a multi-product post, correct proposed product cards, approve them, and see exactly which facts the assistant may use. A customer image, post caption, or model guess never becomes a product fact by itself.

### Stage 2: validate the assistant with a manual reply copilot

**Work:** Seller supplies a buyer's message and any relevant media; assistant searches the approved catalog and policies, then drafts a reply for the seller to copy into the native inbox. When a fact is missing, it produces a clear seller question instead of guessing. Use the same catalog and conversation rules intended for the integrated assistant.

**Gate:** Pilot sellers judge replies useful and natural in real Tunisian-language examples. Track edits, unsafe factual claims, product-match correctness, handoffs, and time saved. Do not claim automatic replies or reduced response time until measured.

### Stage 3: prove order capture and handoff

**Work:** Build the buyer conversation flow around one question at a time. Collect product/variant/quantity per item and delivery address/phone; show a complete summary; wait for explicit buyer confirmation; then create a pending seller-review request. The seller accepts or rejects it. If the assistant lacks a delivery, payment, stock, or policy answer, it asks the seller and never saves a private answer as shared shop knowledge without approval.

**Gate:** Missing information is requested, corrections return to buyer confirmation, duplicate message events cannot create duplicate replies or requests, and owner takeover pauses automation for that conversation.

### Stage 4: connect official channels one at a time

**Work:** Complete Meta verification, App Review, permission requests, webhook setup, account onboarding, opt-in and message-window handling, media download, and delivery-status tracking. Validate WhatsApp coexistence limitations and merchant billing before onboarding sellers. Then add Messenger with its separate review and Page-post permissions. Use the manual copilot until each official integration is approved and live-tested.

**Gate:** A live pilot shop can connect, receive a buyer event once, produce a safe answer or handoff, and send only through the official API within platform rules. A failed token, unavailable API, duplicate event, or provider timeout leaves the message visible and does not trigger a guessed response.

### Stage 5: price and expand only from pilot evidence

**Work:** Measure model tokens, image/audio work, platform template charges, partner fees, hosting, support, and usage by shop. Test quality, response latency, and safe-handoff behavior on seller-reviewed Tunisian Arabic, Arabizi, Arabic-French, and French cases. Set the included allowance and overage after actual costs and seller willingness to pay are known.

**Gate:** Publish pricing only when the cost model includes provider, platform, hosting, and support costs and a clear margin target. Add more product categories or channels only after the apparel workflow works reliably.

## Keep out of the first release

TikTok and Instagram messaging, Facebook comment automation, unofficial browser automation, voice replies, automatic stock reservation, exact stock promises without a trusted source, payment processing, shipping integrations, and automatic fulfillment.

## Cross-stage acceptance checks

- The assistant only uses seller-approved facts and identifies stale/unknown availability as unknown.
- It matches the buyer's language when reliable, asks one relevant follow-up at a time, and does not repeat already supplied details.
- It escalates unknown answers to the seller with enough context to answer quickly.
- It never claims a request is accepted, stock reserved, payment completed, or delivery guaranteed before the seller confirms it.
- It preserves message order, deduplicates retries, and pauses safely on account, provider, or delivery failures.
- Each shop's catalog, messages, and order requests remain isolated; customer details stay out of diagnostic logs.
- The pilot measures seller edits, unsafe claims, correct product matches, handoffs, order completeness, p95 latency, and cost per shop.
