import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

DATA_DIR = Path(__file__).resolve().parent.parent
CONNECTIONS_FILE = DATA_DIR / "people_connections.json"

connections_store: Dict[str, dict] = {}


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


def connection_key(email_a: str, email_b: str) -> str:
    first, second = sorted([email_a.lower(), email_b.lower()])
    return f"{first}::{second}"


def load_connections() -> None:
    global connections_store
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONNECTIONS_FILE.exists():
        CONNECTIONS_FILE.write_text("{}", encoding="utf-8")
    loaded = _load_json(CONNECTIONS_FILE)
    connections_store = {k: v for k, v in loaded.items() if isinstance(v, dict)}


def save_connections() -> None:
    _save_json(CONNECTIONS_FILE, connections_store)


def get_connection(email_a: str, email_b: str) -> Optional[dict]:
    return connections_store.get(connection_key(email_a, email_b))


def connection_status(viewer: str, other: str) -> str:
    conn = get_connection(viewer, other)
    if not conn or conn.get("status") == "removed":
        return "none"
    status = conn.get("status")
    if status == "accepted":
        return "accepted"
    if status == "pending":
        if conn.get("from") == viewer.lower():
            return "pending_outgoing"
        return "pending_incoming"
    return "none"


def can_people_chat(viewer: str, other: str) -> bool:
    return connection_status(viewer, other) == "accepted"


def _partner_profile(email: str, users: dict, build_avatar, ws_connections: dict) -> dict:
    data = users.get(email, {})
    return {
        "email": email,
        "name": data.get("name") or email.split("@", 1)[0],
        "avatar": data.get("avatar") or build_avatar(email),
        "online": email in ws_connections,
    }


def list_requests(viewer_email: str, users: dict, build_avatar, ws_connections: dict) -> dict:
    incoming = []
    outgoing = []
    for conn in connections_store.values():
        if conn.get("status") != "pending":
            continue
        from_email = conn.get("from", "")
        to_email = conn.get("to", "")
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
    existing = connections_store.get(key)
    now = datetime.now(tz=timezone.utc).isoformat()

    if existing:
        status = existing.get("status")
        if status == "accepted":
            raise HTTPException(status_code=409, detail="You are already connected.")
        if status == "pending":
            if existing.get("from") == from_email:
                raise HTTPException(status_code=409, detail="Request already sent.")
            raise HTTPException(status_code=409, detail="This user already sent you a request.")

    record = {
        "id": key,
        "from": from_email,
        "to": to_email,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    connections_store[key] = record
    save_connections()
    return record


def accept_request(viewer_email: str, request_id: str, users: dict) -> dict:
    conn = connections_store.get(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("to") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to accept this request.")

    conn["status"] = "accepted"
    conn["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    connections_store[request_id] = conn
    save_connections()
    return conn


def reject_request(viewer_email: str, request_id: str) -> dict:
    conn = connections_store.get(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("to") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to reject this request.")

    connections_store.pop(request_id, None)
    save_connections()
    return {"message": "Request rejected."}


def list_accepted_connections(
    viewer_email: str, users: dict, build_avatar, ws_connections: dict
) -> List[dict]:
    viewer_email = viewer_email.lower()
    partners = []
    for conn in connections_store.values():
        if conn.get("status") != "accepted":
            continue
        from_email = conn.get("from", "")
        to_email = conn.get("to", "")
        if viewer_email not in (from_email, to_email):
            continue
        partner_email = to_email if from_email == viewer_email else from_email
        partners.append(_partner_profile(partner_email, users, build_avatar, ws_connections))
    return partners


def cancel_request(viewer_email: str, request_id: str) -> dict:
    conn = connections_store.get(request_id)
    if not conn or conn.get("status") != "pending":
        raise HTTPException(status_code=404, detail="Request not found.")
    if conn.get("from") != viewer_email.lower():
        raise HTTPException(status_code=403, detail="Not allowed to cancel this request.")

    connections_store.pop(request_id, None)
    save_connections()
    return {"message": "Request cancelled."}


def remove_connection(viewer_email: str, partner_email: str) -> dict:
    partner_email = partner_email.lower()
    key = connection_key(viewer_email, partner_email)
    conn = connections_store.get(key)
    if not conn or conn.get("status") != "accepted":
        raise HTTPException(status_code=404, detail="Connection not found.")

    connections_store.pop(key, None)
    save_connections()
    return {"message": "Connection removed.", "partner": partner_email}


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
