# Product specification: AI sales assistant for Tunisian shops

**Status:** Draft for Aziz's review
**Version:** 0.1
**Market:** Tunisia
**Initial category:** Apparel
**Channels:** Facebook Page Messenger and WhatsApp Business

## 1. Product purpose

Help small Tunisian apparel sellers answer repetitive customer messages and capture complete order requests without requiring a website, online store, or existing product database.

The assistant may answer routine questions from seller-approved shop information. It must ask for missing order details, avoid inventing product facts, and route uncertainty or sensitive requests to the shop owner. The owner remains responsible for accepting an order and fulfilling it.

This is a hosted service for independent shops. It is not a general chatbot and does not replace the seller's judgment.

## 2. Users

### Shop owner

A solo seller or small shop owner who manages customer conversations through Facebook Page Messenger and WhatsApp Business. The owner connects the shop's official business accounts, maintains product information, reviews order requests, and handles exceptions.

### Customer

A person messaging a shop to ask about products, price, variants, availability, delivery, payment, or how to buy. Customers may write in Tunisian Arabic, Arabic, French, a mixture of Arabic and French, or Arabizi.

## 3. Core customer outcomes

- Get a quick, accurate answer to routine questions.
- Learn what product and variant information the shop has confirmed.
- Submit an order request without repeating information across several messages.
- Reach the shop owner when the assistant cannot safely answer.


## 4. First-release scope

### Included

- Facebook Page Messenger and WhatsApp Business messaging through official Meta business APIs, subject to review and account eligibility.
- One owner account per shop.
- A shop-managed apparel catalog, usable without a website or database.
- New-product capture from connected Facebook Page posts. New posts create reviewable product-import batches; sellers can also submit a post or image manually if feed access is unavailable.
- Text replies in Tunisian Arabic, Arabic, French, Arabic-French code-switching, and Arabizi. Mirror the customer's language when the assistant can do so reliably. Use a shop-configured fallback when it cannot.
- Incoming product photos and screenshots are matched against approved catalog items. Voice notes are transcribed for product and order interpretation; unclear media is handed to the owner.
- Routine answers grounded in approved catalog facts and shop policies.
- Multi-item order requests, with a separate product, variant, and quantity for every item.
- A review queue for uncertain questions, incomplete purchase intent, and order requests awaiting the seller.
- Email notifications for new handoffs, with the in-app queue as the authoritative record.
- Per-shop internal cost and usage metering.

### Excluded from the first release

- TikTok messaging, Instagram Direct, Facebook post-comment automation, and personal or unofficial messaging-account automation.
- Voice replies. Incoming voice notes are transcribed for product search; unclear transcripts go to the owner.
- Automatic product publication or stock changes based only on social posts. Posts produce drafts, never verified facts.
- Identifying a product from a customer image without matching it against approved catalog entries. Ambiguous matches go to the owner.
- Live POS, ERP, or inventory-system synchronization. The shop must keep app-managed stock current or accept that availability becomes unknown.
- Payment processing, shipping-provider integrations, automatic stock reservation, and automatic fulfillment.
- Staff roles and multi-user shop accounts.

Human-like means natural language and shop tone—not impersonating a human. If asked whether it is automated, the assistant answers truthfully; any proactive disclosure required by law or platform rules is included.

### Pilot fallback while Meta access is pending

If API approval is delayed, validate with a manual reply copilot: the seller pastes or uploads a customer message, receives a grounded draft, then copies it into the native inbox. This does not access or send through the inbox and is not a substitute for the intended integrated product. Use the same approved catalog, order flow, and safety rules so the learning carries forward. Pursue Meta onboarding and App Review in parallel; never bypass them with unofficial automation.

Each shop maintains seller-approved knowledge in three scopes: shop-wide policies and preferences (for example delivery coverage, fees, timing, payment, returns, tone, and language); product facts attached to a specific product or variant (for example price, size, color, material, and availability); and conversation-only answers that apply to one customer thread. Product facts override shop-wide defaults only for that product. Conversation-only answers never become shared knowledge automatically. When scopes conflict or a fact is missing or stale, the assistant asks the seller rather than guessing.

The seller interface provides a simple instruction/fact entry flow with an explicit scope selector, preview of what the assistant will use, edit/deactivate controls, and source and last-updated metadata. Prefer structured fields for repeatable facts and policies; allow plain-language instructions for tone and response behavior, but do not let them override safety rules, verified product data, or platform requirements. Saving a handoff answer as reusable knowledge requires the seller to choose shop-wide or selected-product scope and confirm the resulting entry.

The knowledge store must retain the active value, scope, seller, source, and update time, with change history sufficient to identify and reverse incorrect updates. Conflicting active entries must be surfaced for seller resolution; do not silently choose one. Retrieval uses only active, seller-approved entries for the current shop and relevant product. Measure handoff rate alongside factual-error rate: fewer handoffs are not a success if unsupported answers increase.

Each shop connects one or both supported channels: a Facebook Page in Messenger and/or a WhatsApp Business account supported by the official platform APIs. Account eligibility, permissions, number setup, and onboarding must be tested with pilot shops before implementation promises a frictionless setup.

The app keeps a structured, seller-approved catalog. It works without a website or database. Each product has a stable ID and may have multiple sellable variants. Each variant has at least:

- Product name and customer-facing description.
- Price and currency, expected to be TND for the Tunisia launch.
- One or more seller-approved product images.
- Size and color when applicable.
- Availability per variant: available, sold out, or unknown. Exact quantity is not used to answer customers in v1.
- Last-updated time and source for price and stock.

For v1, do not promise exact stock counts. Add exact counts only if the shop records every stock change or connects a trusted live source. If that condition is not met, the assistant reports only the last seller-confirmed availability or asks the owner.

The catalog is the source of truth for customer answers. Existing Meta Commerce catalog data may seed it after permissions are approved. A Facebook post, customer image, conversation, or model extraction does not become a fact until the seller approves it.

For shops without an external inventory source, the owner updates availability in the app, including sales made outside the connected channels. If the shop does not keep that information current, the assistant must treat availability as unknown and ask the owner. A recent post is not evidence that a variant is still in stock. Automatic stock reservation and live inventory synchronization are out of scope for the first release.

### Product post capture

When the connected Page publishes a new post, a Meta feed webhook can signal the change. The app retrieves the post text and attachments and creates an import batch. It suggests separate structured product cards for clearly distinct attached product images. A collage, ambiguous caption, or unclear product count stays in seller review; the seller can split, combine, edit, or discard candidates. The seller approves each product's name, price, variants, and availability before the assistant can use them. Sellers can also paste a post caption and upload its images to create the same reviewable cards when feed access is unavailable. The app should show a concise preview of the facts the assistant will use. A generated prompt may be offered as a preview or export, but it is not the product record or source of truth.

Page feed monitoring depends on Page permissions, app installation, and Meta app review. Post capture must not silently update an existing product or its stock.

## 6. Conversation behavior

Before classification, normalize the incoming content. Use text as written; transcribe audio; and process images or screenshots into searchable visual/text clues. Search only the shop's approved catalog and policies. Media interpretation proposes a match; it does not create product or inventory facts.

1. Identify the customer's intent from text, transcript, attachment, and conversation context.
2. Retrieve candidate products from the shop's approved catalog using the customer's description, image, screenshot text, or voice transcript.
3. Answer automatically only when the product match is clear, the relevant product facts are current, and the request is low risk.
4. Ask the customer to choose between plausible product matches, or ask a concise follow-up for missing details.
5. Escalate when the assistant cannot understand the message, the match remains ambiguous, product information is stale, or the request is consequential.

The assistant may answer only from the shop's approved information for topics such as product details, price, variants, availability, delivery areas and fees, payment methods, business hours, and return or exchange policies. The shop must provide a policy before the assistant answers that topic. Missing policy means ask the owner, not infer a standard practice.

If the assistant does not know an answer, it tells the customer it will check and creates an owner handoff with the unanswered question, conversation context, and relevant product or policy references. The owner supplies a direct answer or identifies an approved source. The assistant must not invent an answer. The owner explicitly approves any answer saved as reusable shop knowledge.

For a customer photo or screenshot, the assistant may describe visual clues and retrieve matching catalog items. It must not treat a general vision model's caption as proof of a specific item, variant, price, or stock. If several similar products match, show a short choice or hand off to the owner. Voice transcripts may help identify a product, but the customer must confirm all order details in the order summary before the app saves an order request.

The assistant must not claim that stock is reserved, an order is accepted, a payment succeeded, or delivery is guaranteed unless the shop has explicitly confirmed that state. If asked whether it is AI or automated, it must answer truthfully. Proactive disclosure wording and timing must be checked against applicable local law and current platform rules before launch.

## 7. Order-request workflow

An order request is a customer's confirmed request to buy. It is not an accepted or fulfilled order.

### Required information

For each item:

- Selected product.
- Size and color when that product has those variants.
- Quantity.

For the request:

- Delivery address.
- Customer phone number.

The customer name is optional unless a shop's delivery process requires it. The product may configure additional required fields only when the owner's process needs them.

### Flow and states

1. **Collecting details:** The assistant extracts order details from the conversation. It asks for missing required fields. The shop can see an incomplete lead, but the product must not present it as an order request.
2. **Awaiting customer confirmation:** When required fields are present, the assistant shows the customer a concise summary of every item, variant, quantity, phone number, and address.
3. **Pending seller review:** Only after the customer explicitly confirms that summary does the system create an order request and place it in the owner's queue.
4. **Accepted or rejected:** The owner reviews the request and explicitly accepts or rejects it in the app. The assistant may notify the customer of that decision only after the owner acts.
5. **Fulfillment:** The seller handles payment, delivery, stock reservation, and fulfillment outside the product in the first release.

An incomplete lead and a pending seller-review request must remain distinct. A correction to a confirmed summary returns it to customer confirmation before the system creates or updates the request. Duplicate delivery of the same platform event must not create duplicate order requests or replies.

## 8. Human handoff

The owner can pause automation for the whole shop. A handoff includes the conversation, reason for escalation, relevant approved catalog or policy references, and any suggested draft reply. The owner can answer directly or provide an answer for the current customer.
When the assistant does not know an answer, it tells the customer it will check and creates an owner handoff containing the unanswered question, conversation context, and relevant product or policy references. The owner supplies a direct answer or points to an approved source. The assistant must not invent an answer or claim a human has already checked.

The owner must explicitly choose whether to save a provided answer as reusable shop information. The system must not learn a shop policy from a private exchange without that choice.

The in-app queue is the source of truth. Email notifications alert the owner to new work. If email delivery fails, the item remains visible in the queue and the system records the notification failure. While an item awaits an owner, the shop may enable a short, approved holding response such as "I'll check this for you." The response must not invent a promised reply time.

When the owner takes over a conversation, automatic replies for that conversation pause until the owner resumes them. This prevents the assistant and seller from replying over each other.

## 9. Safety, privacy, and access

- Each shop's catalog, conversations, order requests, settings, usage, and logs must remain isolated from other shops.
- Each shop has one owner account in the first release. The owner can pause automation and review all shop data.
- Use customer data only to provide the service to that shop. Do not use private messages to train a shared model.
- Collect only the data needed to answer the customer or prepare the request. Treat phone numbers and addresses as sensitive personal data.
- Keep conversation history separate from order records. Provide shop-level deletion controls and define exact retention periods before pilot launch, after checking Tunisia's applicable legal requirements and the seller's operational needs.
- Do not put message contents, addresses, or phone numbers in diagnostic logs unless the owner explicitly needs them in the product UI.
- Verify the sender and event at platform boundaries. Keep a record of automated replies, human handoffs, seller approvals, order-state changes, and account changes.
- If a product fact is unavailable or the assistant cannot parse a message safely, hold rather than guess.

## 10. Reliability and performance

The provisional target is for routine text replies to complete in under 10 seconds in at least 95% of requests while required providers and platforms are healthy. Treat this as a pilot target, not a service-level promise, until measurements support it.

The product must:

- Fail closed when an AI provider times out, returns malformed output, or cannot support the language or request. Do not send a speculative reply.
- Keep the incoming message visible and notify the owner if automated handling fails.
- Pause the affected channel and alert the owner when a business-account token expires or platform delivery fails persistently.
- Deduplicate platform webhook events and make reply and order creation safe to retry.
- Preserve per-conversation message order, or hold the conversation if the order cannot be established.
- Show delivery and processing status so the owner can distinguish received, answered, held, failed, and seller-reviewed work.
- Provide a shop-wide pause control and a conversation-level handoff control.

Before launch, test retries, duplicate webhooks, provider timeouts, expired account credentials, missing product facts, multi-product Page posts, similar apparel images, screenshots, mixed-language voice transcripts, and owner takeover. Build evaluation cases from seller-approved Tunisian Arabic, Arabic, French, code-switching, and Arabizi examples. Measure transcript quality, product-match accuracy, and unsafe sends separately from needless handoffs.

## 11. Usage and pricing model

The first commercial model is a monthly shop subscription with an included allowance of AI-processed incoming messages and an overage charge. The shop sees a clear usage count. The business internally records actual costs by shop, channel, provider, model, and processing type.

The demonstration may use a free hosted model with synthetic data only. Do not send real buyer messages, names, phone numbers, addresses, or seller secrets to a provider's free tier unless its data terms have been reviewed and approved for that use. Free quota, latency, and availability are not production guarantees.

Choose production models after testing seller-reviewed Tunisian Arabic, Arabizi, French, code-switching, grounded product answers, order extraction, safe handoff, p95 latency, price, availability, and data terms. Start with one model that meets the quality bar. Add lower-cost or specialized models only when measurements show that routing them improves cost without reducing safety or answer quality.

Track per-shop usage and spend by text, image, audio/transcription, model, and provider. Use a base subscription with a measured included allowance and overage. Add per-shop spend alerts and a hard limit; when reached, pause automation and notify the owner rather than silently degrading answer quality.

For shop `s` in month `m`, estimate cost as:

`C(s,m) = Σ AI call costs + Σ media-processing costs + platform messaging fees + allocated hosting and operations`

For model call `j`:

`AI call cost(j) = input_tokens(j) × input_rate(j) + output_tokens(j) × output_rate(j)`

Rates must use the provider's current price units, including any per-million-token conversion. Measure product-image extraction, customer-image matching, and voice transcription separately. WhatsApp voice media may need conversion before transcription; include conversion and provider costs in the shop's internal usage record.

If target gross margin is `g`, a cost-based floor for revenue covering measured cost `C` is:

`revenue_floor = C / (1 - g)`

For usage beyond the included allowance, calculate a conservative overage floor from measured marginal cost per billable message, including platform fees and a safety margin. Use pilot data, not one average message, because message length and processing cost vary. This floor is not the final price: compare it with seller willingness to pay and the value of time saved.

Count one billable unit for each unique customer message processed by an AI provider, whether the result is an automated answer or a handoff. Exclude human-only handling, duplicate platform events, and internal retries. Report provider spend separately from customer-visible usage. Do not publish prices until provider rates, Meta charges, hosting allocation, support costs, and pilot usage have been measured.

## 12. Pilot success measures

Record a baseline for each pilot shop before automation. Compare:

- Seller time spent on repetitive messages.
- Median and p95 first-response time.
- Percentage of order requests complete at first seller review.
- Percentage of automated replies accepted without seller correction.
- Correct top product match for customer text, images, screenshots, and voice notes, measured against seller-reviewed examples.
- Unsafe product or policy claims sent to customers. Target: zero known unsafe sends in the evaluation set and pilot review.
- Handoff rate and reasons for handoff.
- Order requests accepted or rejected by sellers.
- Actual provider, platform, hosting, and support cost per shop and per billable message.

Do not claim conversion lift from a small pilot unless the test can attribute it. Use pilot results to set targets and decide whether to expand beyond apparel or add integrations.

## 13. Platform and launch constraints

Use Meta's official business APIs. WhatsApp allows free-form service replies during the 24-hour customer-service window; outside that window, businesses must use approved templates. WhatsApp recipients must have opted in to receive messages. Messenger uses a 24-hour standard messaging window for responses. The product must respect these constraints and surface a clear error or handoff when a message cannot be sent.

Serving other businesses requires more than developer-only test access. WhatsApp Tech Provider onboarding requires Meta business verification, App Review, and Advanced Access for the permissions used; merchant businesses must complete onboarding and billing. Messenger requires App Review for public third-party use. Reading Page posts requires separate Page permissions and Page tasks from messaging access. Meta approval is not guaranteed. If review is delayed, the manual reply-copilot pilot is the supported fallback.

For sellers using an existing WhatsApp Business app number, Coexistence may be available through Embedded Signup, but it has prerequisites and unsupported app features. Explain these and Cloud API billing before onboarding. Do not promise unchanged workflows until a real pilot account is tested.

Meta currently charges for delivered template messages by category and recipient country/region. Non-template replies within an open 24-hour customer-service window are free; utility templates delivered in that window are also free. Tunisia's `+216` is mapped to Rest of Africa; international customers may be billed at other market rates. Rates can change, so use Meta's current rate card for forecasts. Keep Meta/partner fees separate from AI usage and subscription charges; prefer seller-direct Meta billing for the pilot and disclose any partner fee.

Meta supports Page feed webhooks for Page changes. WhatsApp image and audio messages arrive as media events. Download media promptly: WhatsApp media URLs expire after five minutes, and webhook media IDs are available for seven days. If a shop has a connected WhatsApp catalog, structured product messages and cart-order webhooks can provide product IDs and quantities instead of relying on free-text extraction.

Sources checked on 2026-10-17:

- [WhatsApp Cloud API: send messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages)
- [Messenger Platform: send messages](https://developers.facebook.com/docs/messenger-platform/send-messages)
- [Meta Webhooks for Pages](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages)
- [Meta Page Feed API](https://developers.facebook.com/docs/graph-api/reference/page/feed/)
- [Messenger webhooks](https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks)
- [WhatsApp image webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/image)
- [WhatsApp audio webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/audio)
- [WhatsApp media API](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)
- [Meta catalog fields](https://developers.facebook.com/documentation/ads-commerce/commerce-platform/catalog/fields)
- [WhatsApp order webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/order)
- [OpenAI speech-to-text](https://developers.openai.com/api/docs/guides/speech-to-text)

- [WhatsApp Tech Provider onboarding](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers/)
- [WhatsApp App Review](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/app-review)
- [Messenger App Review](https://developers.facebook.com/documentation/business-messaging/messenger-platform/app-review)
- [WhatsApp pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
Before implementation, verify current permissions, account eligibility, onboarding, webhook requirements, regional availability, pricing, and automation-disclosure rules against Meta's current documentation and a live pilot account. Test Tunisian dialect transcription before enabling audio-driven automatic answers. Do not use unofficial browser automation for commercial messaging.

## Research tooling

Use REA during product research to inspect competitor apps and authorized storefront flows. REA is a development-time tool, not a customer-facing dependency or part of each shop's bill.

## 15. Decisions already made

- Tunisia is the primary launch market, with an initial focus on apparel sellers.
- First channels are Facebook Page Messenger and WhatsApp Business.
- Official business APIs are required.
- Shops without websites or databases can manage a catalog directly.
- Connected Facebook Page posts can create multi-product draft batches; sellers can also submit posts or images manually. The owner approves product facts and stock before customer use.
- Text, image, screenshot, and voice-note inputs search the approved catalog. Ambiguous matches and unclear transcripts go to the owner. Voice replies are excluded.
- Order requests can contain multiple items and require customer confirmation before seller review.
- The seller accepts or rejects requests in the app. Payment and delivery remain outside the first release.
- The owner account is the only shop role in v1.
- The hosted service isolates shops and does not train a shared model on customer conversations.
- Subscription includes a usage allowance, with overage based on AI-processed inbound messages.
- If Meta review is delayed, validate with the manual reply copilot; do not bypass platform approval.
- Sellers add new arrivals through approved product cards generated from post text/images; generated prompts are optional previews, not catalog truth.
- When the agent lacks an answer, it asks the seller/owner directly and saves the answer as reusable shop knowledge only after approval.
- Replies mirror the buyer's natural language and shop tone without claiming or implying the agent is human.
- Keep WhatsApp platform charges separate from the subscription and AI usage; prefer seller-direct billing during the pilot.

## 16. Items to validate before planning implementation

These are validation tasks, not features to assume:

- Confirm that pilot sellers can connect their existing Facebook Pages and WhatsApp Business accounts through Meta's supported setup.
- Verify whether the chosen Meta APIs allow the proposed inbound and reply flows for each account type and what permissions/review steps they require.
- Verify Meta business verification requirements and confirm the project owner can complete them before relying on first-party WhatsApp Tech Provider onboarding. Meta currently requests business details (name, address, phone, email, website), a way to verify the business connection, and supporting documents if it cannot find the business. No verification attempt has been made.
- Compare seller-direct Meta billing with solution-partner fees before onboarding; use the current Meta rate card for recipient-region pricing.
- Test account setup and number migration or coexistence with the seller's current workflow. Do not promise that existing numbers can be connected without change until tested.
- Check Tunisia-specific privacy, retention, and automation-disclosure obligations with reliable local guidance.
- Measure Tunisian Arabic, Arabizi, Arabic-French code-switching, and French answer quality with real seller-reviewed text and voice examples.
- Test Page feed permissions and post retrieval with a pilot Page, including one post with several product images and one collage. Confirm the owner can correct, split, and approve product drafts.
- Confirm whether pilot sellers will maintain per-variant availability for sales that happen outside connected channels; exact counts require recording every stock movement or connecting a live source.
- Run a pilot to measure latency, model and platform costs, handoff frequency, and seller willingness to pay.
- Compare AI providers and models on Tunisian-language answer quality, unsafe-send rate, p95 latency, total cost per shop, and data terms. Choose after the evaluation set and pilot tests, not from token price alone.
- Set exact data-retention periods, gross-margin target, monthly allowance, and overage price from legal review and pilot evidence.
