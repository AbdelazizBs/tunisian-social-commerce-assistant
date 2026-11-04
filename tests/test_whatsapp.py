import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from shop_assistant.main import create_app


def _signed(body: bytes, secret: str) -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"x-hub-signature-256": f"sha256={digest}"}


def test_webhook_rejects_a_bad_signature_and_stores_text_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    body = json.dumps({
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [
                        {
                            "id": "wamid.1",
                            "from": "21600000000",
                            "type": "text",
                            "text": {"body": "9adech wa9t?"},
                        },
                        {
                            "id": "wamid.2",
                            "from": "21600000000",
                            "type": "image",
                            "image": {"id": "media"},
                        },
                    ]
                }
            }]
        }]
    }).encode()
    with TestClient(app) as client:
        challenge = client.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "123",
        })
        rejected = client.post("/api/v1/whatsapp/webhook", content=body)
        headers = _signed(body, "app-secret")
        accepted = client.post("/api/v1/whatsapp/webhook", content=body, headers=headers)
        again = client.post("/api/v1/whatsapp/webhook", content=body, headers=headers)
        inbox = client.get("/api/v1/whatsapp/inbox")

    assert challenge.status_code == 200
    assert challenge.json() == 123
    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert again.status_code == 200
    rows = inbox.json()
    assert len(rows) == 2
    assert rows[1]["text"] == "9adech wa9t?"
    assert rows[0]["kind"] == "image"
    assert rows[0]["text"] == ""


def test_send_without_whatsapp_credentials_does_not_call_meta(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'app.db'}")
    body = json.dumps({
        "entry": [{"changes": [{"value": {"messages": [
            {"id": "wamid.9", "from": "21600000000", "type": "text", "text": {"body": "salut"}},
        ]}}]}]
    }).encode()
    with TestClient(app) as client:
        client.post("/api/v1/whatsapp/webhook", content=body, headers=_signed(body, "app-secret"))
        response = client.post("/api/v1/whatsapp/messages/1/send", json={"text": "Marhba"})

    assert response.status_code == 503
    assert "WHATSAPP_TOKEN" in response.json()["detail"]
