"""
services/people_service.py — Connection persistence via Supabase `connections` table.

Public API is identical to the old file-based version so that main.py
requires no changes.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import supabase


# ---------------------------------------------------------------------------
# Startup hook — no-op with Supabase
# ---------------------------------------------------------------------------

def load_connections() -> None:
    """No-op: data lives in Supabase, not files."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def connection_key(email_a: str, email_b: str) -> str:
    first, second = sorted([email_a.lower(), email_b.lower()])
    return f"{first}::{second}"


def _get_connection(key: str) -> Optional[dict]:
    res = (
        supabase.table("connections")
        .select("*")
        .eq("id", key)
        .maybe_single()
        .execute()
    )
    return res.data  # None when not found


def _save_connection(record: dict) -> None:
    supabase.table("connections").upsert(record).execute()


def _delete_connection(key: str) -> None:
    supabase.table("connections").delete().eq("id", key).execute()


def _partner_profile(email: str, users: dict, build_avatar, ws_connections: dict) -> dict:
    data = users.get(email, {})
    return {
        "email": email,
        "name": data.get("name") or email.split("@", 1)[0],
        "avatar": data.get("avatar") or build_avatar(email),
        "online": email in ws_connections,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_connection(email_a: str, email_b: str) -> Optional[dict]:
    return _get_connection(connection_key(email_a, email_b))


def connection_status(viewer: str, other: str) -> str:
    conn = get_connection(viewer, other)
    if not conn or conn.get("status") == "removed":
        return "none"
    status = conn.get("status")
    if status == "accepted":
        return "accepted"
    if status == "pending":
        if conn.get("from_email") == viewer.lower():
            return "pending_outgoing"
        return "pending_incoming"
    return "none"


def can_people_chat(viewer: str, other: str) -> bool:
    return connection_status(viewer, other) == "accepted"


def list_requests(viewer_email: str, users: dict, build_avatar, ws_connections: dict) -> dict:
    res = (
        supabase.table("connections")
        .select("*")
        .eq("status", "pending")
        .or_(f"from_email.eq.{viewer_email},to_email.eq.{viewer_email}")
        .execute()
    )
    rows = res.data or []

    incoming = []
    outgoing = []
    for conn in rows:
        from_email = conn.get("from_email", "")
        to_email = conn.get("to_email", "")
        if to_email == viewer_email:
            incoming.append(
                {
                    "id": conn["id"],
                    "from": _partner_profile(from_email, users, build_avatar, ws_connections),
                    "created_at": conn.get("created_at"),
                }
            )
        elif from_email == viewer_email:
            outgoing.append(
                {
                    "id": conn["id"],
                    "to": _partner_profile(to_email, users, build_avatar, ws_connections),
                    "created_at": conn.get("created_at"),
                }
            )
    return {"incoming": incoming, "outgoing": outgoing}


def send_request(from_email: str, to_email: str, users: dict) -> dict:
    from_email = from_email.lower()
    to_email = to_email.lower()

    if from_email == to_email:
        raise HTTPException(status_code=400, detail="Cannot send a request to yourself.")
    if to_email not in users:
        raise HTTPException(status_code=404, detail="User not found.")

    key = connection_key(from_email, to_email)
    existing = _get_connection(key)
    now = datetime.now(tz=timezone.utc).isoformat()

    if existing:
        status = existing.get("status")
        if status == "accepted":
            raise HTTPException(status_code=409, detail="You are already connected.")
        if status == "pending":
            if existing.get("from_email") == from_email:
                raise HTTPException(status_code=409, detail="Request already sent.")
            raise HTTPException(status_code=409, detail="This user already sent you a request.")

    record = {
        "id": key,
        "from_email": from_email,
        "to_email": to_email,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    _save_connection(record)
    # Return with "from"/"to" keys so main.py notification code works unchanged
    return {**record, "from": from_email, "to": to_email}


def accept_request(viewer_email: str, request_id: str, users: dict) -> dict:
    conn = _get_connection(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("to_email") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to accept this request.")

    now = datetime.now(tz=timezone.utc).isoformat()
    conn["status"] = "accepted"
    conn["updated_at"] = now
    _save_connection(conn)
    # Expose "from"/"to" for notification code in main.py
    return {**conn, "from": conn["from_email"], "to": conn["to_email"]}


def reject_request(viewer_email: str, request_id: str) -> dict:
    conn = _get_connection(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("to_email") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to reject this request.")

    _delete_connection(request_id)
    return {"message": "Request rejected."}


def cancel_request(viewer_email: str, request_id: str) -> dict:
    conn = _get_connection(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("from_email") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to cancel this request.")

    _delete_connection(request_id)
    return {"message": "Request cancelled."}


def remove_connection(viewer_email: str, partner_email: str) -> dict:
    partner_email = partner_email.lower()
    key = connection_key(viewer_email, partner_email)
    conn = _get_connection(key)
    if not conn or conn.get("status") != "accepted":
        raise HTTPException(status_code=404, detail="Connection not found.")

    _delete_connection(key)
    return {"message": "Connection removed.", "partner": partner_email}


def list_accepted_connections(
    viewer_email: str, users: dict, build_avatar, ws_connections: dict
) -> List[dict]:
    viewer_email = viewer_email.lower()
    res = (
        supabase.table("connections")
        .select("*")
        .eq("status", "accepted")
        .or_(f"from_email.eq.{viewer_email},to_email.eq.{viewer_email}")
        .execute()
    )
    rows = res.data or []

    partners = []
    for conn in rows:
        from_email = conn.get("from_email", "")
        to_email = conn.get("to_email", "")
        partner_email = to_email if from_email == viewer_email else from_email
        partners.append(_partner_profile(partner_email, users, build_avatar, ws_connections))
    return partners


def enrich_people_matches(matches: List[dict], viewer_email: str) -> List[dict]:
    enriched = []
    for item in matches:
        email = item.get("email", "")
        row = dict(item)
        row["connectionStatus"] = connection_status(viewer_email, email)
        conn = get_connection(viewer_email, email)
        if conn and conn.get("status") == "pending":
            row["requestId"] = conn["id"]
        enriched.append(row)
    return enriched
