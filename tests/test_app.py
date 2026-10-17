from fastapi.testclient import TestClient

from shop_assistant.main import create_app


def test_product_upsert_is_idempotent_and_updates_approved_facts(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        first = client.put(
            "/api/v1/products/robe-bleue",
            json={"name": "Robe bleue", "price_tnd": "65.000", "availability": "available"},
        )
        updated = client.put(
            "/api/v1/products/robe-bleue",
            json={"name": "Robe bleue", "price_tnd": "69.000", "availability": "unknown"},
        )
        listed = client.get("/api/v1/products")

    assert first.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["id"] == first.json()["id"]
    assert updated.json()["price_tnd"] == "69.000"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_no_catalog_returns_seller_prompt_without_model_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post("/api/v1/replies/draft", json={"message": "قداش سومو؟"})

    assert response.status_code == 200
    assert response.json()["draft"] == {
        "reply_text": "",
        "matched_product_ids": [],
        "needs_seller": True,
        "seller_question": "Add an approved product card before drafting product replies.",
    }


def test_configured_catalog_without_model_key_fails_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        client.put(
            "/api/v1/products/robe-bleue",
            json={"name": "Robe bleue", "price_tnd": "65.000", "availability": "available"},
        )
        response = client.post("/api/v1/replies/draft", json={"message": "قداش سوم الروبة؟"})

    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
