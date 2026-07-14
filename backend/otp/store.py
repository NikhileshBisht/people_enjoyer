"""
otp/store.py — OTP persistence via Supabase.

Public API is identical to the old file-based OtpStore so that
service.py and main.py require no changes.
"""
from datetime import datetime, timezone
from typing import Optional

from db import supabase


class OtpStore:
    """Thin wrapper around the Supabase `otp_store` table."""

    # ------------------------------------------------------------------
    # Compatibility shim: main.py calls otp_store.load() on startup.
    # With Supabase there is nothing to load from disk.
    # ------------------------------------------------------------------
    def load(self) -> None:
        pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def get(self, key: str) -> Optional[dict]:
        """Return the OTP record for *key*, or None if not found."""
        res = (
            supabase.table("otp_store")
            .select("otp,expires_at")
            .eq("key", key)
            .maybe_single()
            .execute()
        )
        return res.data  # None when no row found

    def set(self, key: str, record: dict) -> None:
        """Insert or replace the OTP record for *key*."""
        supabase.table("otp_store").upsert(
            {
                "key": key,
                "otp": record["otp"],
                "expires_at": record["expires_at"],
            }
        ).execute()

    def pop(self, key: str) -> None:
        """Delete the OTP record for *key* (if it exists)."""
        supabase.table("otp_store").delete().eq("key", key).execute()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def purpose_key(email: str, purpose: str) -> str:
        return f"{purpose}:{email.lower()}"

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def cleanup_expired(self) -> None:
        """Delete all rows whose expires_at is in the past."""
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        supabase.table("otp_store").delete().lt("expires_at", now_iso).execute()
