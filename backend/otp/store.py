import json
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import OTP_DIR, OTP_STORE_FILE

LEGACY_OTP_STORE_FILE = OTP_DIR.parent / "otp_store.json"


class OtpStore:
    def __init__(self) -> None:
        self._records: Dict[str, dict] = {}

    def load(self) -> None:
        OTP_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not OTP_STORE_FILE.exists() and LEGACY_OTP_STORE_FILE.exists():
            OTP_STORE_FILE.write_text(
                LEGACY_OTP_STORE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
            )
        if not OTP_STORE_FILE.exists():
            OTP_STORE_FILE.write_text("{}", encoding="utf-8")
            self._records = {}
            return
        try:
            content = OTP_STORE_FILE.read_text(encoding="utf-8").strip()
            if not content:
                self._records = {}
                return
            loaded = json.loads(content)
            self._records = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._records = {}

    def save(self) -> None:
        OTP_STORE_FILE.write_text(json.dumps(self._records, indent=2), encoding="utf-8")

    def get(self, key: str) -> Optional[dict]:
        return self._records.get(key)

    def set(self, key: str, record: dict) -> None:
        self._records[key] = record
        self.save()

    def pop(self, key: str) -> None:
        if key in self._records:
            self._records.pop(key)
            self.save()

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
        now = datetime.now(tz=timezone.utc)
        expired_keys = []
        for key, record in self._records.items():
            expires_at = record.get("expires_at")
            if not expires_at:
                expired_keys.append(key)
                continue
            try:
                expires_dt = self._parse_iso_datetime(expires_at)
            except ValueError:
                expired_keys.append(key)
                continue
            if now > expires_dt:
                expired_keys.append(key)
        for key in expired_keys:
            self._records.pop(key, None)
        if expired_keys:
            self.save()
