import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from fastapi import HTTPException

DATA_DIR = Path(__file__).resolve().parent.parent
CURRENCY_CHAT_FILE = DATA_DIR / "currency_chat_store.json"
PEOPLE_CHAT_FILE = DATA_DIR / "people_chat_store.json"
LEGACY_CHAT_FILE = DATA_DIR / "chat_store.json"

CHAT_MODULES = {"currency", "people"}

currency_chat_store: Dict[str, List[dict]] = {}
people_chat_store: Dict[str, List[dict]] = {}


def _store_for_module(module: str) -> Dict[str, List[dict]]:
    if module == "currency":
        return currency_chat_store
    if module == "people":
        return people_chat_store
    raise HTTPException(status_code=400, detail="Invalid chat module.")


def _chat_file_for_module(module: str) -> Path:
    return CURRENCY_CHAT_FILE if module == "currency" else PEOPLE_CHAT_FILE


def _load_json(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        loaded = json.loads(content)
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _thread_key(email_a: str, email_b: str) -> str:
    first, second = sorted([email_a.lower(), email_b.lower()])
    return f"{first}::{second}"


def load_chats() -> None:
    global currency_chat_store, people_chat_store
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if LEGACY_CHAT_FILE.exists() and not CURRENCY_CHAT_FILE.exists():
        legacy = _load_json(LEGACY_CHAT_FILE)
        currency_chat_store = {k: v for k, v in legacy.items() if isinstance(v, list)}
        _save_json(CURRENCY_CHAT_FILE, currency_chat_store)
    else:
        loaded_currency = _load_json(CURRENCY_CHAT_FILE)
        currency_chat_store = {k: v for k, v in loaded_currency.items() if isinstance(v, list)}

    loaded_people = _load_json(PEOPLE_CHAT_FILE)
    people_chat_store = {k: v for k, v in loaded_people.items() if isinstance(v, list)}

    for path in (CURRENCY_CHAT_FILE, PEOPLE_CHAT_FILE):
        if not path.exists():
            _save_json(path, {})


def save_chats(module: str) -> None:
    store = _store_for_module(module)
    _save_json(_chat_file_for_module(module), store)


def create_message(sender: str, recipient: str, text: str) -> dict:
    return {
        "id": f"msg-{int(datetime.now(tz=timezone.utc).timestamp() * 1000)}-{random.randint(1000, 9999)}",
        "sender": sender.lower(),
        "recipient": recipient.lower(),
        "text": text.strip(),
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "read": False,
    }


def send_message(
    module: str,
    sender: str,
    recipient: str,
    text: str,
    *,
    users: dict,
    can_message: Optional[Callable[[str, str], bool]] = None,
) -> dict:
    module = module.lower()
    if module not in CHAT_MODULES:
        raise HTTPException(status_code=400, detail="Invalid chat module.")

    recipient = recipient.lower()
    sender = sender.lower()
    if recipient == sender:
        raise HTTPException(status_code=400, detail="Cannot message yourself.")
    if recipient not in users:
        raise HTTPException(status_code=404, detail="Recipient not found.")

    if can_message and not can_message(sender, recipient):
        raise HTTPException(
            status_code=403,
            detail="You must be connected to message this person.",
        )

    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(clean_text) > 1000:
        raise HTTPException(status_code=400, detail="Message is too long.")

    store = _store_for_module(module)
    thread = _thread_key(sender, recipient)
    message = create_message(sender, recipient, clean_text)
    message["module"] = module
    store.setdefault(thread, []).append(message)
    save_chats(module)
    return message


def list_conversations(
    module: str,
    viewer_email: str,
    *,
    users: dict,
    ws_connections: dict,
    build_avatar,
    partner_filter: Optional[Callable[[str, str], bool]] = None,
) -> List[dict]:
    store = _store_for_module(module)
    conversations = []
    for thread_key, messages in store.items():
        left, right = thread_key.split("::", 1)
        if viewer_email not in (left, right):
            continue
        partner = right if left == viewer_email else left
        if partner_filter and not partner_filter(viewer_email, partner):
            continue
        partner_user = users.get(partner, {})
        unread_count = sum(
            1 for m in messages if m.get("recipient") == viewer_email and not m.get("read", False)
        )
        last_message = messages[-1] if messages else None
        conversations.append(
            {
                "partner": {
                    "email": partner,
                    "name": partner_user.get("name") or partner.split("@", 1)[0],
                    "avatar": partner_user.get("avatar") or build_avatar(partner),
                    "online": partner in ws_connections,
                },
                "last_message": last_message,
                "unread_count": unread_count,
            }
        )

    conversations.sort(
        key=lambda item: (item.get("last_message") or {}).get("sent_at", ""),
        reverse=True,
    )
    return conversations


def get_messages(
    module: str,
    viewer_email: str,
    partner_email: str,
    *,
    users: dict,
    ws_connections: dict,
    build_avatar,
) -> dict:
    store = _store_for_module(module)
    partner_email = partner_email.lower()
    thread = _thread_key(viewer_email, partner_email)
    messages = store.get(thread, [])
    changed = False
    for msg in messages:
        if msg.get("recipient") == viewer_email and not msg.get("read", False):
            msg["read"] = True
            changed = True
    if changed:
        save_chats(module)

    partner = users.get(partner_email, {})
    return {
        "module": module,
        "partner": {
            "email": partner_email,
            "name": partner.get("name") or partner_email.split("@", 1)[0],
            "avatar": partner.get("avatar") or build_avatar(partner_email),
            "online": partner_email in ws_connections,
        },
        "messages": messages,
    }
