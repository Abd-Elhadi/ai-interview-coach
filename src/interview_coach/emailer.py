"""Send the approved PDF report through the Resend HTTPS API."""
import base64
import os
import time
from pathlib import Path

import httpx

API_URL = "https://api.resend.com/emails"
MAX_PER_HOUR = 3
_sent: dict = {}


class EmailError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY"))


def _check_rate(user_id: int) -> None:
    now = time.time()
    recent = [t for t in _sent.get(user_id, []) if now - t < 3600]
    if len(recent) >= MAX_PER_HOUR:
        raise EmailError(f"Email limit reached ({MAX_PER_HOUR} per hour). Try again later.")
    _sent[user_id] = recent + [now]


def send_report(user_id: int, to_email: str, pdf_path: str, score: float) -> None:
    """The recipient is always the signed-in account email, never free text."""
    key = os.getenv("RESEND_API_KEY")
    if not key:
        raise EmailError("Email is not configured on this deployment.")
    _check_rate(user_id)
    payload = {
        "from": os.getenv("EMAIL_FROM", "AI Interview Coach <onboarding@resend.dev>"),
        "to": [to_email],
        "subject": f"Your interview coaching report ({score:.1f}/5)",
        "text": "Your approved interview coaching report is attached.\n\nPractice coaching estimate. Not a hiring decision.",
        "attachments": [
            {"filename": "interview_report.pdf", "content": base64.b64encode(Path(pdf_path).read_bytes()).decode()}
        ],
    }
    try:
        response = httpx.post(API_URL, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=20)
    except httpx.HTTPError as err:
        raise EmailError(f"Could not reach the email service: {err}")
    if response.status_code >= 300:
        detail = ""
        try:
            detail = str(response.json().get("message", ""))[:200]
        except ValueError:
            pass
        raise EmailError(f"Email service error ({response.status_code}). {detail}".strip())