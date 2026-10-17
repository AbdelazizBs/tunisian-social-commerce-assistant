# Technical architecture

**Status:** Draft for review
**Product:** Tunisian shop assistant
**Stack requested:** Python, FastAPI, LangChain, LangGraph when justified
**Decision state:** Proposed architecture. Meta access, production model, hosting, and final persistence deployment remain unverified.

## Goal

Build a hosted multi-tenant application with strict shop-data isolation. Start with a manual reply copilot, then add official Meta messaging integrations without replacing the catalog, order rules, or evaluation harness.

## Decisions

| Concern | Decision | Why |
| --- | --- | --- |
| Application shape | Python modular monolith with FastAPI | Keeps domain rules local while giving us a deployable API; split services only after measured need. |
| Persistence | SQLModel; SQLite for local development, PostgreSQL for hosted shops | One model layer for a zero-setup local run and a transactional production database. Add Alembic migrations before a pilot that stores real shop data. |
| Reply generation | LangChain `ChatGroq` with strict JSON-schema output; approved product facts go in the request context | The app already loaded the shop's catalog. A tool loop adds latency/cost and Groq explicitly does not combine tool use with Structured Outputs in one request. |
| Workflow orchestration | No custom LangGraph graph in the first slice | This demo is one stateless draft request. Add explicit graph/checkpoint control when live conversations need pause/resume across seller handoffs and restarts. |
| Critical asynchronous work | Durable database-backed inbox/outbox plus a separate worker when Meta webhooks arrive | FastAPI in-process background tasks are not a durable job queue. Meta retries duplicate WhatsApp webhooks; persist and deduplicate before returning success. |
| Verification | Pytest for deterministic behavior; a small synthetic-data model eval harness | Separates business-rule regressions from model-quality and cost changes. |

This is the chosen architecture, not a menu. A local SQLite database is for learning and demo only; hosted multi-shop data uses PostgreSQL.

## Role of REA

REA is a developer research tool, not part of the product runtime. Its [README](https://github.com/morluto/rea) describes an MCP-connected reverse-engineering toolkit for inspecting applications, websites, and binaries and returning evidence-backed findings. We can use it during product discovery to inspect publicly accessible competitor flows or our own test application, subject to access rights and terms. Do not ship REA as a dependency, use it to access private customer accounts, or treat its findings as a substitute for official Meta API documentation.

Our product's customer-facing assistant remains a separate Python/FastAPI application using LangChain. The two tools solve different problems: REA helps us investigate software; LangChain helps our application interpret a shop conversation.

## Proposed system shape

Keep business rules in ordinary Python modules, expose them through FastAPI, and use SQLModel over SQLite locally and PostgreSQL for hosted shops. Do not split services before measured load requires it.

```mermaid
flowchart LR
    Seller[Seller dashboard and manual copilot] --> API[FastAPI]
    Meta[Meta webhooks, later] --> API
    API --> App[Application use cases]
    App --> Domain[Catalog, conversation, order rules]
    App --> Model[Groq structured-output call]
    App --> DB[(SQLModel: SQLite local / PostgreSQL hosted)]
    API -. later Meta webhook .-> Queue[Durable inbox/outbox]
    Queue --> Worker[Separate worker, later]
    Worker --> App
    App --> Channel[Official Meta send adapters, later]
    Eval[Offline evaluation harness] --> App
```

The model never sends messages, edits stock, or confirms orders directly. Application code validates the proposed answer and state transition before any side effect.

## Modules and proposed file layout

```text
src/shop_assistant/
├── api/                 # FastAPI routes, auth, webhook validation
├── application/         # Reply, catalog import, order, handoff, usage use cases
├── domain/              # Shop, product, conversation, order states and rules
├── agents/              # LangChain harness, tools, structured output
├── adapters/            # PostgreSQL, model provider, media storage, Meta channels
└── jobs/                # Durable inbound event processing

evals/
├── cases/               # Seller-reviewed synthetic and consented examples
├── run.py               # Replays cases and records quality, latency, and cost
└── README.md            # How to run and interpret the harness
```

This is a proposed layout, not a claim about existing source files. Keep the first demo smaller if its implementation does not need a module yet.

## Request flow

### Manual copilot demo

1. In the local demo, the seller creates an approved product card in SQLite through the API; hosted shops will use PostgreSQL.
2. The seller submits a buyer's text message. The application loads the shop-scoped approved products and policy context.
3. LangChain sends the buyer message and approved catalog facts in one request and validates a typed reply draft or seller handoff using Groq JSON Schema output.
4. Application code checks the proposed evidence and decision. The demo shows the draft and any seller question; it never sends to a customer.
5. Record provider, model, token usage, and latency for each model call. Durable per-shop billing records are added before commercial rollout.

### Official channel flow, after Meta approval

1. Verify the webhook signature and parse the channel payload at the FastAPI boundary.
2. Insert the platform event under a unique channel event ID and return success promptly. Duplicate deliveries resolve to the existing event.
3. A worker claims the stored event, downloads temporary media promptly, and records normalized message evidence.
4. The application loads the shop's approved catalog, policies, conversation state, and any open order request.
5. The assistant may propose an answer or handoff. Deterministic application rules own order transitions, missing required fields, price/stock safety, opt-in, and channel messaging-window checks.
6. Validate the reply and its evidence. If validation fails or required facts are missing, hold and notify the owner. Otherwise send through the official channel adapter and record the delivery result.

## Model and workflow boundaries

The demo sends only the current buyer message and that shop's approved catalog to the model. The catalog is already loaded by the application, so a model tool call would add an unnecessary round trip. Use a read-only tool loop only when the agent must choose among external capabilities that are not already available to the application.

Keep these rules in deterministic Python code: evidence IDs must belong to the loaded catalog; required order fields, one-question-at-a-time progression, customer confirmation, seller accept/reject, availability freshness, duplicate prevention, and account/channel limits. A model suggests values; the domain validates and owns state changes. Groq does not support tool use and Structured Outputs in the same request, so keep those request modes separate.

## Data and reliability

- SQLModel owns the local demo's product records in SQLite. Hosted shops use PostgreSQL for shops, channel connections, products, variants, policies, conversations, order requests, handoffs, webhook events, usage, and audit records.
- Every hosted shop-owned query and write carries a shop identity. Enforce tenant isolation at the repository boundary and test cross-shop access before onboarding a second shop.
- Store media outside the relational database when production media support is added. Persist its shop, purpose, expiry, and deletion state. Download expiring channel media promptly after event acceptance.
- For official webhooks, persist events before acknowledging them, deduplicate by platform event ID, and preserve per-conversation ordering. Retries must converge without duplicate replies or orders.
- Save outbound intent and provider result so retries cannot send duplicate replies. Distinguish received, processing, held, sent, failed, and seller-reviewed states.
- Keep secrets in environment or a secret manager. Do not log message bodies, phone numbers, or addresses by default.
- Add per-shop usage and spend ceilings. If a ceiling is reached, hold automation and alert the owner; never silently switch to a lower-quality model.

## Model selection and cost control

Groq is the proposed free-demo provider for `openai/gpt-oss-20b`, using synthetic data only. Groq's rate-limit page lists 30 requests/minute, 1,000/day, 8,000 tokens/minute, and 200,000/day for this model, while describing its table as base Developer-plan limits. Verify the account's free-tier model access and live limits before the demo; the organization limits page is authoritative. The app requires a seller-supplied `GROQ_API_KEY`; it starts without one, but reply generation returns an explicit configuration error. Never send real customer data to a free-tier service.

For production, compare models on Tunisian Arabic, Arabizi, French, code-switching, grounded product accuracy, order extraction, handoff precision, p95 latency, token cost, availability, and data terms. Start with one model. Add cheaper routing or separate image/audio models only if measured savings preserve the quality bar.

Meter input and output tokens, image operations, audio duration/transcription, retries, and provider/model per shop. Keep Meta template charges and partner fees separate from model cost, especially when sellers pay Meta directly. Set allowance and overage from pilot workload and seller willingness to pay, with a gross-margin floor and a per-shop hard spend limit.

## Harness and evaluations

Create an offline runner that sends reviewed cases through the same reply and domain path used by the app, with no live channel sends. Use synthetic examples until sellers approve use of real examples.

Each case records the shop facts, buyer message or media reference, expected product/variant or handoff, required order fields, allowed claims, language style, and expected safety outcome. Score correctness and safety separately from fluency. Keep exact phrasing flexible. Track product-match accuracy, unsupported claims, missing-field handling, handoff decisions, latency, token/media usage, and cost.

Use deterministic tests for order state transitions, tenant isolation, duplicate webhooks, retry behavior, and platform-window checks. Use a small seller-reviewed model evaluation set for language quality and grounding. Human reviewers remain the source of truth for Tunisian dialect quality; a model judge can help triage cases but cannot replace them.

## Learning path while building

1. **FastAPI:** follow one request from route validation to a typed response. Learn how routers, dependencies, and lifespan resources fit together.
2. **Domain logic:** trace a confirmed buyer order through pure state transitions. Learn why the model does not own order state.
3. **LangChain:** inspect the `ChatGroq` structured-output schema, approved facts in the prompt, token usage, and one real synthetic evaluation request. Add `create_agent` and tools later when the workflow needs model-directed external actions.
4. **LangGraph:** add durable checkpointing only when the live workflow needs a real pause/resume after seller handoff. Compare a resumed thread with the durable domain record.
5. **Harness and evals:** run one reviewed Tunisian-language case, inspect the answer, evidence, latency, and cost, then add cases when a failure is discovered.

Code comments will explain non-obvious boundaries and safety invariants, not repeat what each line already says. Each implementation slice will include a short plain-language explanation alongside the code.

## First implementation slice

Build a FastAPI local app that lets a seller add an approved product card to SQLite and request one grounded draft reply or a seller handoff. Use LangChain strict JSON-schema output, deterministic evidence validation, per-call usage reporting, and two synthetic evaluation cases. No Meta integration, media ingestion, order persistence, production auth, or automatic message sending in this slice.

## Decisions to confirm before production integration

- Confirm PostgreSQL hosting, migration, backup, and retention requirements before a real-data pilot.
- Verify the Groq API key's organization limits and current data terms before using even synthetic demo traffic.
- Select the paid production model only after the seller-reviewed evaluation set exists.
- Validate whether sellers require WhatsApp Coexistence before finalizing channel onboarding.
- Before a pilot, add durable webhook inbox/outbox processing, idempotent channel adapters, and a persistent checkpoint strategy for live handoffs.

## References

- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [Groq Structured Outputs and tool-use limitation](https://console.groq.com/docs/structured-outputs)
- [LangChain agents and `create_agent` for later tool-driven workflows](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain ChatGroq integration](https://docs.langchain.com/oss/python/integrations/chat/groq)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [FastAPI background tasks and limitations](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Messenger App Review](https://developers.facebook.com/documentation/business-messaging/messenger-platform/app-review)
- [WhatsApp webhook overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview)
- [Product specification](product-spec.md)
- [Product delivery plan](product-plan.md)
