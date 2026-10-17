# Model evaluation harness

`run.py` exercises the running FastAPI application against synthetic cases. It writes demo products through the idempotent SKU endpoint, then evaluates the result against expected handoff and catalog-evidence outcomes.

Run from the repository root after starting the server and setting `GROQ_API_KEY`:

```powershell
uv run python evals/run.py
```

These two cases are smoke-level examples, not a quality benchmark. They consume the configured provider's free quota. Inspect Tunisian Arabic and French output with a fluent seller; machine checks cannot establish naturalness or dialect quality. Never add real customer messages, personal data, or seller secrets to these cases without an approved data-handling decision.
