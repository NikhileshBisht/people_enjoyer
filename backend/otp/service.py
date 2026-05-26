import random
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict

from fastapi import HTTPException

from .email_sender import send_otp_email
from .config import OTP_EXPIRY_MINUTES
from .store import OtpStore


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


class OtpService:
    def __init__(
        self,
        store: OtpStore,
        users: Dict[str, dict],
        save_users: Callable[[], None],
        create_access_token: Callable[[str], str],
    ) -> None:
        self.store = store
        self.users = users
        self.save_users = save_users
        self.create_access_token = create_access_token

    def request_register_otp(self, email: str) -> dict:
        self.store.cleanup_expired()
        if email in self.users:
            raise HTTPException(status_code=409, detail="User already registered.")

        otp = generate_otp()
        send_otp_email(email, otp, "registration")
        key = OtpStore.purpose_key(email, "register")
        self.store.set(
            key,
            {
                "otp": otp,
                "expires_at": (
                    datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
                ).isoformat(),
            },
        )
        return {"message": "Registration OTP sent to your email. Check your inbox."}

    def verify_register_otp(self, email: str, otp: str) -> dict:
        self.store.cleanup_expired()
        key = OtpStore.purpose_key(email, "register")
        record = self.store.get(key)
        if not record:
            raise HTTPException(status_code=400, detail="Registration OTP not requested.")
        if datetime.now(tz=timezone.utc) > OtpStore._parse_iso_datetime(record["expires_at"]):
            self.store.pop(key)
            raise HTTPException(status_code=400, detail="Registration OTP expired.")
        if otp.strip() != record["otp"]:
            raise HTTPException(status_code=400, detail="Invalid OTP.")

        self.users[email] = {"email": email, "created_at": datetime.now(tz=timezone.utc).isoformat()}
        self.save_users()
        self.store.pop(key)
        token = self.create_access_token(email)
        return {
            "message": "Registration successful.",
            "access_token": token,
            "token_type": "bearer",
        }

    def request_login_otp(self, email: str) -> dict:
        self.store.cleanup_expired()
        if email not in self.users:
            raise HTTPException(status_code=404, detail="User not found. Please register first.")

        otp = generate_otp()
        send_otp_email(email, otp, "login")
        key = OtpStore.purpose_key(email, "login")
        self.store.set(
            key,
            {
                "otp": otp,
                "expires_at": (
                    datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
                ).isoformat(),
            },
        )
        return {"message": "Login OTP sent to your email. Check your inbox."}

    def verify_login_otp(self, email: str, otp: str) -> dict:
        self.store.cleanup_expired()
        key = OtpStore.purpose_key(email, "login")
        record = self.store.get(key)
        if not record:
            raise HTTPException(status_code=400, detail="Login OTP not requested.")
        if datetime.now(tz=timezone.utc) > OtpStore._parse_iso_datetime(record["expires_at"]):
            self.store.pop(key)
            raise HTTPException(status_code=400, detail="Login OTP expired.")
        if otp.strip() != record["otp"]:
            raise HTTPException(status_code=400, detail="Invalid OTP.")

        self.store.pop(key)
        token = self.create_access_token(email)
        return {
            "message": "Login successful.",
            "access_token": token,
            "token_type": "bearer",
        }
