import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Tuple

from fastapi import HTTPException

from .config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    smtp_is_configured,
)
from .email_template import build_otp_html, build_otp_plain_text

logger = logging.getLogger(__name__)


def _smtp_password() -> str:
    return (SMTP_PASSWORD or "").replace(" ", "").strip()


def _delivery_attempts() -> List[Tuple[str, int]]:
    """Prefer SSL/465 for Gmail; fall back to STARTTLS/587."""
    attempts: List[Tuple[str, int]] = []
    if SMTP_PORT == 465:
        attempts.append(("ssl", 465))
    elif SMTP_PORT == 587:
        attempts.append(("starttls", 587))
        attempts.append(("ssl", 465))
    else:
        attempts.append(("starttls", SMTP_PORT))
        attempts.append(("ssl", 465))
    return attempts


def _send_with_mode(mode: str, port: int, message: EmailMessage) -> None:
    password = _smtp_password()
    context = ssl.create_default_context()

    if mode == "ssl":
        with smtplib.SMTP_SSL(SMTP_HOST, port, timeout=30, context=context) as server:
            server.login(SMTP_USER, password)
            server.send_message(message)
        return

    with smtplib.SMTP(SMTP_HOST, port, timeout=30) as server:
        server.ehlo()
        if not server.has_extn("STARTTLS"):
            raise smtplib.SMTPException("STARTTLS not supported by server.")
        server.starttls(context=context)
        server.ehlo()
        server.login(SMTP_USER, password)
        server.send_message(message)


def send_otp_email(email: str, otp: str, purpose: str) -> None:
    subject = "Verify Your Account — MacNik"
    plain_body = build_otp_plain_text(otp, purpose)
    html_body = build_otp_html(otp, purpose)

    if not smtp_is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Email is not configured on the server. "
                "Create backend/.env from .env.example with your SMTP settings, "
                "then restart uvicorn."
            ),
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    errors: List[str] = []
    for mode, port in _delivery_attempts():
        try:
            _send_with_mode(mode, port, message)
            logger.info("OTP email sent to %s via %s:%s", email, mode, port)
            return
        except smtplib.SMTPAuthenticationError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "SMTP login failed. For Gmail, use an App Password "
                    "(not your normal password): https://myaccount.google.com/apppasswords"
                ),
            ) from exc
        except smtplib.SMTPException as exc:
            errors.append(f"{mode} on port {port}: {exc}")
        except OSError as exc:
            errors.append(f"{mode} on port {port}: {exc}")

    raise HTTPException(
        status_code=502,
        detail=(
            "Could not send email. "
            + "; ".join(errors)
            + ". Try SMTP_PORT=465 in backend/.env and restart the server."
        ),
    )
