# Tunisian Social Commerce Assistant

A local reply copilot for Tunisian shop sellers. It lets a seller save approved product facts and ask for a grounded draft reply. It never sends messages. Unknown facts produce a seller handoff instead of a guess.

## Stack decisions

- **FastAPI** exposes the local API and its interactive docs at `/docs`.
- **SQLModel + SQLite** persist the local demo catalog. Hosted shops will use PostgreSQL.
- **LangChain `ChatGroq` structured output** drafts replies from the approved catalog context. This avoids an unnecessary tool loop and uses synthetic data only.
- **No custom LangGraph workflow yet.** Add explicit checkpointing when live conversations need durable pause/resume for seller handoffs.
- **Pytest and `evals/`** separate deterministic app behavior from model-quality evaluation.

See [`technical-architecture.md`](technical-architecture.md), [`product-spec.md`](product-spec.md), and [`product-plan.md`](product-plan.md).

## Run locally

Requires Python 3.12+ and `uv`.

```powershell
uv sync
$env:GROQ_API_KEY = "your-groq-api-key"
uv run fastapi dev
```

Open <http://127.0.0.1:8000/docs>. Add or update a product with `PUT /api/v1/products/{sku}`, then draft a reply with `POST /api/v1/replies/draft`. The local database is `.local/app.db`.

Get a Groq API key from <https://console.groq.com/keys>. Without a key, the app still starts and catalog endpoints work; reply generation returns an explicit `503` configuration error. Use synthetic product/message data only with the free-tier provider. Do not put customer messages, names, phone numbers, addresses, or seller secrets into the demo.

Optional hosted database driver:

```powershell
uv sync --extra postgres
$env:DATABASE_URL = "postgresql+psycopg://user:password@host/database"
```

PostgreSQL hosting, migrations, auth, and retention are not production-ready in this first slice.

## Run checks and model evaluations

```powershell
uv run pytest
uv run ruff check .
uv run python evals/run.py
```

The evaluation runner calls the local app and the configured Groq model using synthetic cases. Start the app first; evaluation calls consume the Groq account's quota. It checks whether known product questions are grounded and unknown policy questions are handed to the seller. Review language quality manually; automatic pass/fail does not prove Tunisian dialect quality.

## Current scope

This is a learning/demo slice: product card CRUD, one text-message reply draft, token/latency reporting, and safe handoff. No Meta connection, automatic replies, image/audio ingestion, order persistence, authentication, or multi-user shop access. Use official Meta APIs only when integration work begins; Meta access and App Review are separate launch gates.
