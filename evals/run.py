import json
import os
import sys
from pathlib import Path

import httpx

BASE_URL = os.getenv("ASSISTANT_URL", "http://127.0.0.1:8000")
CASES = Path(__file__).with_name("cases.jsonl")


def main() -> int:
    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=5)
        health.raise_for_status()
    except httpx.HTTPError:
        print(f"App unavailable at {BASE_URL}; start it with GROQ_API_KEY configured.")
        return 2

    if not health.json().get("model_configured"):
        print(f"No model key is configured in the app at {BASE_URL}.")
        return 2
    failures = 0
    with httpx.Client(base_url=BASE_URL, timeout=45) as client:
        for line in CASES.read_text(encoding="utf-8").splitlines():
            case = json.loads(line)
            product_response = client.put(
                f"/api/v1/products/{case['sku']}",
                json=case["product"],
            )
            product_response.raise_for_status()
            product_id = product_response.json()["id"]

            response = client.post(
                "/api/v1/replies/draft",
                json={"message": case["message"]},
            )
            response.raise_for_status()
            result = response.json()
            draft = result["draft"]
            passed = draft["needs_seller"] is case["expected_needs_seller"]
            if case["expected_sku"]:
                passed = passed and product_id in draft["matched_product_ids"]

            status = "PASS" if passed else "FAIL"
            print(
                f"{status} {case['name']} | model={result['model']} "
                f"latency_ms={result['latency_ms']} usage={result['usage']}"
            )
            print(f"  reply={draft['reply_text']!r} handoff={draft['seller_question']!r}")
            failures += not passed

    print(f"Evaluation cases: {2 - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
