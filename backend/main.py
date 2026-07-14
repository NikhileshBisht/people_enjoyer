import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Any, List

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from db import supabase
from otp import OtpService, OtpStore, init_otp_service, router as otp_router
from services import chat_service, people_service
from enjoyer import router as enjoyer_router

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

app = FastAPI(title="OTP JWT Auth Service")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

# ---------------------------------------------------------------------------
# In-memory user cache — loaded from Supabase on startup, kept in sync.
# Used for fast WebSocket lookups (currency match, people finder).
# All writes go through _save_user() which updates both cache and DB.
# ---------------------------------------------------------------------------
users: Dict[str, dict] = {}
otp_store = OtpStore()
ws_connections: Dict[str, WebSocket] = {}

app.include_router(otp_router)
app.include_router(enjoyer_router)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    to_email: EmailStr
    text: str


class PeopleRequestBody(BaseModel):
    to_email: EmailStr


# ---------------------------------------------------------------------------
# Supabase user helpers
# ---------------------------------------------------------------------------

def _load_users_from_db() -> None:
    """Populate the in-memory cache from the Supabase users table."""
    global users
    res = supabase.table("users").select("*").execute()
    users = {row["email"]: row for row in (res.data or [])}


def _save_user(email: str) -> None:
    record = users.get(email)
    if record is None:
        return

    record_to_save = dict(record)
    record_to_save.pop("id", None)

    supabase.table("users").upsert(
        record_to_save,
        on_conflict="email"
    ).execute()


def _save_users() -> None:
    for email, record in users.items():
        record_to_save = dict(record)
        record_to_save.pop("id", None)

        supabase.table("users").upsert(
            record_to_save,
            on_conflict="email"
        ).execute()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_access_token(email: str) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": email.lower(),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRY_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_bearer(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc

    return payload


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _build_avatar(email: str) -> str:
    name = email.split("@", 1)[0]
    letters = "".join([part[0] for part in name.replace(".", " ").replace("_", " ").split() if part])[:2]
    return letters.upper() or "U"


def _validate_module(module: str) -> str:
    module = module.lower()
    if module not in chat_service.CHAT_MODULES:
        raise HTTPException(status_code=400, detail="Invalid chat module.")
    return module


async def _notify_user(email: str, payload: dict) -> None:
    socket = ws_connections.get(email)
    if socket:
        await socket.send_json(payload)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(min(1.0, a)))


def _build_people_payload(
    viewer_email: str, viewer_lat: float, viewer_lng: float, range_km: float
) -> Dict[str, Any]:
    results = []
    for email, data in users.items():
        if email == viewer_email:
            continue
        if email not in ws_connections:
            continue
        if not data.get("people_finder_live"):
            continue
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is None or lng is None:
            continue
        distance_km = _haversine_km(viewer_lat, viewer_lng, float(lat), float(lng))
        if distance_km > range_km:
            continue
        results.append(
            {
                "id": email,
                "email": email,
                "name": data.get("name") or email.split("@", 1)[0],
                "avatar": data.get("avatar") or _build_avatar(email),
                "bio": data.get("bio") or "Available on People Finder",
                "lat": lat,
                "lng": lng,
                "distanceKm": round(distance_km, 2),
                "online": True,
            }
        )

    results.sort(key=lambda item: item["distanceKm"])
    enriched = people_service.enrich_people_matches(results, viewer_email)
    return {
        "type": "people_matches",
        "rangeKm": range_km,
        "you": {"email": viewer_email, "lat": viewer_lat, "lng": viewer_lng},
        "matches": enriched,
    }


def _build_match_payload(viewer_email: str, from_currency: str, to_currency: str) -> Dict[str, Any]:
    results = []
    for email, data in users.items():
        if email == viewer_email:
            continue
        if email not in ws_connections:
            continue
        if data.get("from_currency") == to_currency and data.get("to_currency") == from_currency:
            lat = data.get("lat")
            lng = data.get("lng")
            if lat is None or lng is None:
                continue
            results.append(
                {
                    "id": email,
                    "email": email,
                    "name": data.get("name") or email.split("@", 1)[0],
                    "avatar": data.get("avatar") or _build_avatar(email),
                    "bio": data.get("bio") or f"Can swap {data.get('from_currency')} to {data.get('to_currency')}",
                    "lat": lat,
                    "lng": lng,
                    "fromCurrency": data.get("from_currency"),
                    "toCurrency": data.get("to_currency"),
                }
            )

    viewer = users.get(viewer_email, {})
    return {
        "type": "matches",
        "for": {"fromCurrency": from_currency, "toCurrency": to_currency},
        "you": {"email": viewer_email, "lat": viewer.get("lat"), "lng": viewer.get("lng")},
        "matches": results,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _load_state() -> None:
    _load_users_from_db()
    otp_store.load()          # no-op with Supabase
    chat_service.load_chats() # no-op with Supabase
    people_service.load_connections()  # no-op with Supabase
    init_otp_service(
        OtpService(
            store=otp_store,
            users=users,
            save_users=_save_users,
            create_access_token=_create_access_token,
        )
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/auth/me")
def me(authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    email = payload.get("sub")
    if not email or email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    return {"email": email}


@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    email = str(payload.get("sub", "")).lower()
    if not email or email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    active_socket = ws_connections.pop(email, None)
    if active_socket:
        try:
            await active_socket.close(code=1000)
        except Exception:
            pass

    return {"message": "Logged out successfully."}


@app.get("/chat/{module}/conversations")
def list_conversations(module: str, authorization: Optional[str] = Header(default=None)):
    module = _validate_module(module)
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    partner_filter = None
    if module == "people":
        partner_filter = people_service.can_people_chat

    conversations = chat_service.list_conversations(
        module,
        viewer_email,
        users=users,
        ws_connections=ws_connections,
        build_avatar=_build_avatar,
        partner_filter=partner_filter,
    )

    if module == "people":
        seen = {item["partner"]["email"] for item in conversations}
        for partner in people_service.list_accepted_connections(
            viewer_email, users, _build_avatar, ws_connections
        ):
            if partner["email"] not in seen:
                conversations.append(
                    {
                        "partner": partner,
                        "last_message": None,
                        "unread_count": 0,
                    }
                )
        conversations.sort(
            key=lambda item: (
                1 if item.get("last_message") else 0,
                (item.get("last_message") or {}).get("sent_at", ""),
            ),
            reverse=True,
        )

    return {"module": module, "conversations": conversations}


@app.get("/chat/{module}/messages/{partner_email}")
def get_messages(
    module: str, partner_email: str, authorization: Optional[str] = Header(default=None)
):
    module = _validate_module(module)
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    partner_email = partner_email.lower()
    if partner_email not in users:
        raise HTTPException(status_code=404, detail="Partner not found.")
    if module == "people" and not people_service.can_people_chat(viewer_email, partner_email):
        raise HTTPException(status_code=403, detail="You must be connected to open this chat.")

    return chat_service.get_messages(
        module,
        viewer_email,
        partner_email,
        users=users,
        ws_connections=ws_connections,
        build_avatar=_build_avatar,
    )


@app.post("/chat/{module}/messages")
async def post_message(
    module: str, request: SendMessageRequest, authorization: Optional[str] = Header(default=None)
):
    module = _validate_module(module)
    payload = _decode_bearer(authorization)
    sender_email = str(payload.get("sub", "")).lower()
    if not sender_email or sender_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    can_message = None
    if module == "people":
        can_message = people_service.can_people_chat

    message = chat_service.send_message(
        module,
        sender_email,
        str(request.to_email),
        request.text,
        users=users,
        can_message=can_message,
    )
    recipient = message["recipient"]
    await _notify_user(
        recipient,
        {"type": "new_message", "module": module, "message": message},
    )
    return {"message": message}


@app.get("/people/requests")
def people_requests(authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    return people_service.list_requests(viewer_email, users, _build_avatar, ws_connections)


@app.post("/people/requests")
async def create_people_request(
    body: PeopleRequestBody, authorization: Optional[str] = Header(default=None)
):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    record = people_service.send_request(viewer_email, str(body.to_email), users)
    await _notify_user(
        record["to"],
        {
            "type": "connection_request",
            "request": {
                "id": record["id"],
                "from": {
                    "email": viewer_email,
                    "name": users.get(viewer_email, {}).get("name")
                    or viewer_email.split("@", 1)[0],
                    "avatar": _build_avatar(viewer_email),
                },
            },
        },
    )
    return {"request": record}


@app.post("/people/requests/{request_id}/accept")
async def accept_people_request(request_id: str, authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    record = people_service.accept_request(viewer_email, request_id, users)
    await _notify_user(
        record["from"],
        {
            "type": "connection_accepted",
            "connection": {
                "id": record["id"],
                "with": {
                    "email": viewer_email,
                    "name": users.get(viewer_email, {}).get("name")
                    or viewer_email.split("@", 1)[0],
                    "avatar": _build_avatar(viewer_email),
                },
            },
        },
    )
    return {"connection": record}


@app.delete("/people/requests/{request_id}")
def cancel_people_request(request_id: str, authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    return people_service.cancel_request(viewer_email, request_id)


@app.post("/people/requests/{request_id}/reject")
def reject_people_request(request_id: str, authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    return people_service.reject_request(viewer_email, request_id)


@app.delete("/people/connections/{partner_email}")
async def delete_people_connection(
    partner_email: str, authorization: Optional[str] = Header(default=None)
):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    result = people_service.remove_connection(viewer_email, partner_email)
    await _notify_user(
        partner_email.lower(),
        {
            "type": "connection_removed",
            "partner": viewer_email,
        },
    )
    return result


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/match")
async def match_socket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = _decode_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    email = str(payload.get("sub", "")).lower()
    if not email or email not in users:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    ws_connections[email] = websocket

    try:
        await websocket.send_json({"type": "connected", "email": email})
        while True:
            raw = await websocket.receive_json()
            message_type = raw.get("type")

            if message_type == "search":
                from_currency = str(raw.get("fromCurrency", "")).upper()
                to_currency = str(raw.get("toCurrency", "")).upper()
                lat = raw.get("lat")
                lng = raw.get("lng")

                if not from_currency or not to_currency:
                    await websocket.send_json({"type": "error", "message": "Currency pair is required."})
                    continue

                user = users[email]
                user["from_currency"] = from_currency
                user["to_currency"] = to_currency
                user["people_finder_live"] = False
                if isinstance(lat, (int, float)):
                    user["lat"] = float(lat)
                if isinstance(lng, (int, float)):
                    user["lng"] = float(lng)
                user["last_seen_at"] = datetime.now(tz=timezone.utc).isoformat()
                users[email] = user
                _save_user(email)

                await websocket.send_json(_build_match_payload(email, from_currency, to_currency))

            elif message_type == "search_people":
                lat = raw.get("lat")
                lng = raw.get("lng")
                range_km = raw.get("rangeKm", 10)

                if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                    await websocket.send_json(
                        {"type": "error", "message": "Your current location is required."}
                    )
                    continue

                try:
                    range_km = float(range_km)
                except (TypeError, ValueError):
                    range_km = 10.0
                range_km = max(0.5, min(100.0, range_km))

                user = users[email]
                user["lat"] = float(lat)
                user["lng"] = float(lng)
                user["people_finder_live"] = True
                user["people_search_range_km"] = range_km
                user["last_seen_at"] = datetime.now(tz=timezone.utc).isoformat()
                users[email] = user
                _save_user(email)

                await websocket.send_json(
                    _build_people_payload(email, float(lat), float(lng), range_km)
                )

            elif message_type == "send_message":
                to_email = str(raw.get("toEmail", "")).lower()
                text = str(raw.get("text", ""))
                module = str(raw.get("module", "currency")).lower()
                if module not in chat_service.CHAT_MODULES:
                    await websocket.send_json({"type": "error", "message": "Invalid chat module."})
                    continue

                can_message = None
                if module == "people":
                    can_message = people_service.can_people_chat

                try:
                    message = chat_service.send_message(
                        module,
                        email,
                        to_email,
                        text,
                        users=users,
                        can_message=can_message,
                    )
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "message": exc.detail})
                    continue

                await websocket.send_json(
                    {"type": "message_sent", "module": module, "message": message}
                )
                await _notify_user(
                    to_email,
                    {"type": "new_message", "module": module, "message": message},
                )
            else:
                await websocket.send_json({"type": "error", "message": "Unsupported event type."})
    except WebSocketDisconnect:
        pass
    finally:
        if ws_connections.get(email) is websocket:
            ws_connections.pop(email, None)
        if email in users:
            users[email]["people_finder_live"] = False
            _save_user(email)


_load_state()
