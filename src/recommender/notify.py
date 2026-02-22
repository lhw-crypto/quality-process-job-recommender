from __future__ import annotations

import os
import requests


def send_email(subject: str, text_body: str, html_body: str | None = None) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_addr = os.getenv("RESEND_FROM", "").strip()
    to_addr = os.getenv("RESEND_TO", "").strip()

    if not api_key or not from_addr or not to_addr:
        return False

    recipients = [x.strip() for x in to_addr.split(",") if x.strip()]
    if not recipients:
        return False

    payload = {
        "from": from_addr,
        "to": recipients,
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return True
    except Exception:
        # Notification failure should not break the recommendation pipeline.
        return False
