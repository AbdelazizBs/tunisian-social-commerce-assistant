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




def test_delivery_facts_are_saved_on_the_shop(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        saved = client.put("/api/v1/shop", json={"delivery_days": 2, "delivery_price_tnd": "7"})
        loaded = client.get("/api/v1/shop")

    assert saved.status_code == 200
    assert loaded.json()["delivery_days"] == 2
    assert loaded.json()["delivery_price_tnd"] == "7.000"


def test_usage_starts_at_zero(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        usage = client.get("/api/v1/usage")

    assert usage.status_code == 200
    assert usage.json()["total_tokens"] == 0
    assert usage.json()["estimated_usd"] == "0.0000"


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


def test_a_bare_hello_still_needs_the_model(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post("/api/v1/replies/draft", json={"message": "hey"})

    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_non_text_share_is_a_seller_handoff_without_a_model(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/replies/draft",
            json={"attachment": "voice"},
        )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["needs_seller"] is True
    assert draft["reply_text"] == ""
    assert draft["seller_question"] == "The buyer shared a voice message. What should I tell them?"
    assert response.json()["model"] == "none"


def test_priority_alerts_start_empty(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.get("/api/v1/alerts")

    assert response.status_code == 200
    assert response.json() == []


def test_seller_approved_facts_are_saved_with_the_product(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/products/robe-ete",
            json={
                "name": "Robe d'été",
                "description": "Noire, taille S",
                "availability": "available",
                "facts": [{"label": "color", "value": "noir"}, {"label": "size", "value": "S"}],
            },
        )
        listed = client.get("/api/v1/products")

    assert saved.status_code == 200
    assert saved.json()["facts"] == [
        {"label": "color", "value": "noir"},
        {"label": "size", "value": "S"},
    ]
    assert listed.json()[0]["facts"][0]["label"] == "color"


def test_empty_description_has_no_facts_without_a_model(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/products/structure",
            json={"name": "Robe", "description": "   ", "availability": "unknown"},
        )

    assert response.status_code == 200
    assert response.json()["facts"] == []


def test_selected_test_discussion_can_be_deleted(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    from sqlmodel import Session

    from shop_assistant.db import engine
    from shop_assistant.models import DiscussionTurn, OrderLead, ShopConversation

    with TestClient(app) as client:
        with Session(engine) as session:
            conversation = ShopConversation(shop_id="demo-shop")
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            session.add(OrderLead(conversation_id=conversation.id, shop_id="demo-shop"))
            session.add(DiscussionTurn(conversation_id=conversation.id, role="buyer", text="slm"))
            session.commit()
            conversation_id = conversation.id
        deleted = client.delete(f"/api/v1/conversations/{conversation_id}")
        listed = client.get("/api/v1/conversations")

    assert deleted.status_code == 204
    assert listed.json() == []


def test_agent_steps_are_listed_newest_first(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        from shop_assistant.services.batch import reset_steps, step

        reset_steps()
        step(4, "waiting", "Quiet window")
        step(4, "failed", "timeout", ok=False)
        rows = client.get("/api/v1/steps").json()

    assert rows[0]["name"] == "failed"
    assert rows[0]["ok"] is False
    assert rows[1]["name"] == "waiting"


def test_unknown_conversation_is_not_found(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.get("/api/v1/conversations/4")

    assert response.status_code == 404


def test_empty_reply_request_is_rejected(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post("/api/v1/replies/draft", json={"message": " "})

    assert response.status_code == 422


def test_instruction_list_starts_empty_and_delete_missing_is_not_found(tmp_path) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        listed = client.get("/api/v1/instructions")
        missing = client.delete("/api/v1/instructions/99")

    assert listed.status_code == 200
    assert listed.json() == []
    assert missing.status_code == 404


def test_adding_an_instruction_requires_a_model_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/instructions",
            json={"text": "Be warm. Delivery to Tunis is 7 TND."},
        )

    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
