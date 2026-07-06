from datetime import date
from html import escape

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.models import RecurringPayment, User


RESEND_EMAIL_URL = "https://api.resend.com/emails"


def send_payment_reminder(user: User, payment: RecurringPayment) -> str:
    if not settings.resend_api_key:
        raise HTTPException(status_code=503, detail="Resend is not configured")
    due = payment.next_due_date.strftime("%d %B %Y")
    safe_name = escape(payment.name)
    amount = f"{payment.amount:.2f} {escape(payment.currency)}"
    html = (
        f"<h2>{safe_name} is due soon</h2>"
        f"<p>Your {escape(payment.kind)} payment of <strong>{amount}</strong> "
        f"is due on <strong>{due}</strong>.</p>"
        "<p>You can review this recurring payment in Finlio.</p>"
    )
    try:
        response = httpx.post(
            RESEND_EMAIL_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [user.email],
                "subject": f"Upcoming payment: {payment.name}",
                "html": html,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not send reminder through Resend") from exc
    return str(data.get("id", "sent"))


def send_password_reset(user: User, reset_token: str) -> str:
    if not settings.resend_api_key:
        raise HTTPException(status_code=503, detail="Resend is not configured")
    reset_url = f"{settings.frontend_url.rstrip('/')}?reset_token={reset_token}"
    safe_name = escape(user.full_name or "there")
    html = (
        f"<h2>Reset your Finlio password</h2>"
        f"<p>Hi {safe_name}, use the button below to choose a new password. "
        "This link expires in 30 minutes.</p>"
        f'<p><a href="{escape(reset_url, quote=True)}" '
        'style="display:inline-block;padding:12px 18px;border-radius:8px;'
        'background:#6538e8;color:#fff;text-decoration:none">Reset password</a></p>'
        "<p>If you did not request this, you can safely ignore this email.</p>"
    )
    try:
        response = httpx.post(
            RESEND_EMAIL_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [user.email],
                "subject": "Reset your Finlio password",
                "html": html,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not send the password reset email") from exc
    return str(data.get("id", "sent"))


def reminder_is_due(payment: RecurringPayment, today: date | None = None) -> bool:
    today = today or date.today()
    days_until_due = (payment.next_due_date - today).days
    already_sent_today = bool(
        payment.last_notified_at and payment.last_notified_at.date() == today
    )
    return payment.is_active and 0 <= days_until_due <= payment.notify_days_before and not already_sent_today
