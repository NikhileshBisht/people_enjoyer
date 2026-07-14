"""
services/chat_service.py — Chat persistence via Supabase `messages` table.

Public API is identical to the old file-based version so that main.py
requires no changes beyond removing the _load_state file calls.
"""
import random
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from fastapi import HTTPException

from db import supabase

CHAT_MODULES = {"currency", "people"}


# ---------------------------------------------------------------------------
# Startup hook — no-op with Supabase (nothing to load from disk)
# ---------------------------------------------------------------------------

def load_chats() -> None:
    """No-op: data lives in Supabase, not files."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _thread_key(email_a: str, email_b: str) -> str:
    first, second = sorted([email_a.lower(), email_b.lower()])
    return f"{first}::{second}"


def _fetch_thread_messages(module: str, email_a: str, email_b: str) -> List[dict]:
    """Return all messages (both directions) for a given thread + module."""
    res = (
        supabase.table("messages")
        .select("*")
        .eq("module", module)
        .or_(
            f"and(sender.eq.{email_a},recipient.eq.{email_b}),"
            f"and(sender.eq.{email_b},recipient.eq.{email_a})"
        )
        .order("sent_at", desc=False)
        .execute()
    )
    return res.data or []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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

    message = create_message(sender, recipient, clean_text)
    message["module"] = module

    supabase.table("messages").insert(
        {
            "id": message["id"],
            "module": module,
            "sender": sender,
            "recipient": recipient,
            "text": clean_text,
            "sent_at": message["sent_at"],
            "read": False,
        }
    ).execute()

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
    # Fetch all messages where the viewer is sender or recipient
    res = (
        supabase.table("messages")
        .select("sender,recipient,text,sent_at,read,id")
        .eq("module", module)
        .or_(f"sender.eq.{viewer_email},recipient.eq.{viewer_email}")
        .order("sent_at", desc=False)
        .execute()
    )
    messages = res.data or []

    # Group by partner
    threads: Dict[str, List[dict]] = {}
    for msg in messages:
        partner = msg["recipient"] if msg["sender"] == viewer_email else msg["sender"]
        threads.setdefault(partner, []).append(msg)

    conversations = []
    for partner, thread_msgs in threads.items():
        if partner_filter and not partner_filter(viewer_email, partner):
            continue
        partner_user = users.get(partner, {})
        unread_count = sum(
            1 for m in thread_msgs
            if m.get("recipient") == viewer_email and not m.get("read", False)
        )
        last_message = thread_msgs[-1] if thread_msgs else None
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
    partner_email = partner_email.lower()
    messages = _fetch_thread_messages(module, viewer_email, partner_email)

    # Mark unread messages as read
    unread_ids = [
        m["id"]
        for m in messages
        if m.get("recipient") == viewer_email and not m.get("read", False)
    ]
    if unread_ids:
        supabase.table("messages").update({"read": True}).in_("id", unread_ids).execute()
        for m in messages:
            if m["id"] in unread_ids:
                m["read"] = True

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
