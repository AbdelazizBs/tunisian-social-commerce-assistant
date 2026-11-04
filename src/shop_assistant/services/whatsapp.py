"""Official WhatsApp Cloud API. Messages are stored until the seller sends a reply."""

import hashlib
import hmac
import json
import os
import urllib.request
from typing import Any

_MEDIA = {"image", "audio", "video", "location"}


def verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    """Return whether the body matches Meta's sha256 signature."""
    if not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256="), digest)


def inbound_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Read text and media notices from a Cloud API webhook. Media is not downloaded."""
    found: list[dict[str, str]] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for message in value.get("messages") or []:
                kind = str(message.get("type") or "other")
                if kind not in _MEDIA and kind != "text":
                    kind = "other"
                body = ""
                if kind == "text":
                    body = str((message.get("text") or {}).get("body") or "")[:4000]
                message_id = str(message.get("id") or "")
                if not message_id:
                    continue
                found.append({
                    "wa_message_id": message_id,
                    "sender": str(message.get("from") or "")[:40],
                    "kind": kind,
                    "text": body,
                })
    return found


def send_text(to: str, body: str) -> None:
    """Send one text reply through the Cloud API. Raises if the token is missing."""
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        raise RuntimeError("WhatsApp is not configured")
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }).encode()
    request = urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{phone_id}/messages",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()
