import os
import random
import smtplib
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Dict, Optional, Any, List

import jwt
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

app = FastAPI(title="OTP JWT Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@example.com")
DEV_EXPOSE_OTP = os.getenv("DEV_EXPOSE_OTP", "true").lower() == "true"

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent))
USERS_FILE = DATA_DIR / "users.json"
OTP_FILE = DATA_DIR / "otp_store.json"
CHAT_FILE = DATA_DIR / "chat_store.json"

users: Dict[str, dict] = {}
otp_store: Dict[str, dict] = {}
ws_connections: Dict[str, WebSocket] = {}
chat_store: Dict[str, List[dict]] = {}


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str


class SendMessageRequest(BaseModel):
    to_email: EmailStr
    text: str


def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("{}", encoding="utf-8")
    if not OTP_FILE.exists():
        OTP_FILE.write_text("{}", encoding="utf-8")
    if not CHAT_FILE.exists():
        CHAT_FILE.write_text("{}", encoding="utf-8")


def _load_json(path: Path) -> Dict[str, dict]:
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        loaded = json.loads(content)
        if isinstance(loaded, dict):
            return loaded
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_json(path: Path, payload: Dict[str, dict]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_state() -> None:
    global users, otp_store, chat_store
    _ensure_data_files()
    users = _load_json(USERS_FILE)
    otp_store = _load_json(OTP_FILE)
    loaded_chats = _load_json(CHAT_FILE)
    chat_store = {k: v for k, v in loaded_chats.items() if isinstance(v, list)}


def _save_users() -> None:
    _save_json(USERS_FILE, users)


def _save_otps() -> None:
    _save_json(OTP_FILE, otp_store)


def _save_chats() -> None:
    _save_json(CHAT_FILE, chat_store)


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cleanup_expired_otps() -> None:
    now = datetime.now(tz=timezone.utc)
    expired_keys = []
    for key, record in otp_store.items():
        expires_at = record.get("expires_at")
        if not expires_at:
            expired_keys.append(key)
            continue
        try:
            expires_dt = _parse_iso_datetime(expires_at)
        except ValueError:
            expired_keys.append(key)
            continue
        if now > expires_dt:
            expired_keys.append(key)
    for key in expired_keys:
        otp_store.pop(key, None)
    if expired_keys:
        _save_otps()


def _purpose_key(email: str, purpose: str) -> str:
    return f"{purpose}:{email.lower()}"


def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


def _send_email_otp(email: str, otp: str, purpose: str) -> None:
    subject = f"Your {purpose} OTP code"
    body = (
        f"Your OTP for {purpose} is: {otp}\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes."
    )

    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = SMTP_FROM
        message["To"] = email
        message.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    else:
        print(f"[DEV EMAIL] to={email} subject={subject} body={body}")


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


def _build_avatar(email: str) -> str:
    name = email.split("@", 1)[0]
    letters = "".join([part[0] for part in name.replace(".", " ").replace("_", " ").split() if part])[:2]
    return letters.upper() or "U"


def _thread_key(email_a: str, email_b: str) -> str:
    first, second = sorted([email_a.lower(), email_b.lower()])
    return f"{first}::{second}"


def _create_message(sender: str, recipient: str, text: str) -> dict:
    return {
        "id": f"msg-{int(datetime.now(tz=timezone.utc).timestamp() * 1000)}-{random.randint(1000, 9999)}",
        "sender": sender.lower(),
        "recipient": recipient.lower(),
        "text": text.strip(),
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "read": False,
    }


def _send_message(sender: str, recipient: str, text: str) -> dict:
    recipient = recipient.lower()
    sender = sender.lower()
    if recipient == sender:
        raise HTTPException(status_code=400, detail="Cannot message yourself.")
    if recipient not in users:
        raise HTTPException(status_code=404, detail="Recipient not found.")
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(clean_text) > 1000:
        raise HTTPException(status_code=400, detail="Message is too long.")

    thread = _thread_key(sender, recipient)
    message = _create_message(sender, recipient, clean_text)
    chat_store.setdefault(thread, []).append(message)
    _save_chats()
    return message


def _conversation_payload(viewer_email: str, partner_email: str, messages: List[dict]) -> dict:
    partner = users.get(partner_email, {})
    unread_count = sum(
        1
        for m in messages
        if m.get("recipient") == viewer_email and not m.get("read", False)
    )
    last_message = messages[-1] if messages else None
    return {
        "partner": {
            "email": partner_email,
            "name": partner.get("name") or partner_email.split("@", 1)[0],
            "avatar": partner.get("avatar") or _build_avatar(partner_email),
            "online": partner_email in ws_connections,
        },
        "last_message": last_message,
        "unread_count": unread_count,
    }


def _build_match_payload(viewer_email: str, from_currency: str, to_currency: str) -> Dict[str, Any]:
    viewer = users.get(viewer_email, {})
    viewer_lat = viewer.get("lat")
    viewer_lng = viewer.get("lng")

    results = []
    for email, data in users.items():
        if email == viewer_email:
            continue
        # Only show users who currently have an active websocket session.
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

    return {
        "type": "matches",
        "for": {"fromCurrency": from_currency, "toCurrency": to_currency},
        "you": {"email": viewer_email, "lat": viewer_lat, "lng": viewer_lng},
        "matches": results,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register/request-otp")
def request_register_otp(request: EmailRequest):
    _cleanup_expired_otps()
    email = request.email.lower()
    if email in users:
        raise HTTPException(status_code=409, detail="User already registered.")

    otp = _generate_otp()
    otp_store[_purpose_key(email, "register")] = {
        "otp": otp,
        "expires_at": (
            datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
        ).isoformat(),
    }
    _save_otps()
    _send_email_otp(email, otp, "registration")

    response = {"message": "Registration OTP sent to email."}
    if DEV_EXPOSE_OTP:
        response["dev_otp"] = otp
    return response


@app.post("/auth/register/verify-otp")
def verify_register_otp(request: VerifyOtpRequest):
    _cleanup_expired_otps()
    email = request.email.lower()
    key = _purpose_key(email, "register")
    record = otp_store.get(key)
    if not record:
        raise HTTPException(status_code=400, detail="Registration OTP not requested.")
    if datetime.now(tz=timezone.utc) > _parse_iso_datetime(record["expires_at"]):
        otp_store.pop(key, None)
        _save_otps()
        raise HTTPException(status_code=400, detail="Registration OTP expired.")
    if request.otp.strip() != record["otp"]:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    users[email] = {"email": email, "created_at": datetime.now(tz=timezone.utc).isoformat()}
    _save_users()
    otp_store.pop(key, None)
    _save_otps()
    token = _create_access_token(email)
    return {"message": "Registration successful.", "access_token": token, "token_type": "bearer"}


@app.post("/auth/login/request-otp")
def request_login_otp(request: EmailRequest):
    _cleanup_expired_otps()
    email = request.email.lower()
    if email not in users:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    otp = _generate_otp()
    otp_store[_purpose_key(email, "login")] = {
        "otp": otp,
        "expires_at": (
            datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
        ).isoformat(),
    }
    _save_otps()
    _send_email_otp(email, otp, "login")

    response = {"message": "Login OTP sent to email."}
    if DEV_EXPOSE_OTP:
        response["dev_otp"] = otp
    return response


@app.post("/auth/login/verify-otp")
def verify_login_otp(request: VerifyOtpRequest):
    _cleanup_expired_otps()
    email = request.email.lower()
    key = _purpose_key(email, "login")
    record = otp_store.get(key)
    if not record:
        raise HTTPException(status_code=400, detail="Login OTP not requested.")
    if datetime.now(tz=timezone.utc) > _parse_iso_datetime(record["expires_at"]):
        otp_store.pop(key, None)
        _save_otps()
        raise HTTPException(status_code=400, detail="Login OTP expired.")
    if request.otp.strip() != record["otp"]:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    otp_store.pop(key, None)
    _save_otps()
    token = _create_access_token(email)
    return {"message": "Login successful.", "access_token": token, "token_type": "bearer"}


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


@app.get("/chat/conversations")
def list_conversations(authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    conversations = []
    for thread_key, messages in chat_store.items():
        left, right = thread_key.split("::", 1)
        if viewer_email not in (left, right):
            continue
        partner = right if left == viewer_email else left
        conversations.append(_conversation_payload(viewer_email, partner, messages))

    conversations.sort(
        key=lambda item: (item.get("last_message") or {}).get("sent_at", ""),
        reverse=True,
    )
    return {"conversations": conversations}


@app.get("/chat/messages/{partner_email}")
def get_messages(partner_email: str, authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    viewer_email = str(payload.get("sub", "")).lower()
    partner_email = partner_email.lower()
    if not viewer_email or viewer_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")
    if partner_email not in users:
        raise HTTPException(status_code=404, detail="Partner not found.")

    thread = _thread_key(viewer_email, partner_email)
    messages = chat_store.get(thread, [])
    changed = False
    for msg in messages:
        if msg.get("recipient") == viewer_email and not msg.get("read", False):
            msg["read"] = True
            changed = True
    if changed:
        _save_chats()

    partner = users.get(partner_email, {})
    return {
        "partner": {
            "email": partner_email,
            "name": partner.get("name") or partner_email.split("@", 1)[0],
            "avatar": partner.get("avatar") or _build_avatar(partner_email),
            "online": partner_email in ws_connections,
        },
        "messages": messages,
    }


@app.post("/chat/messages")
async def post_message(request: SendMessageRequest, authorization: Optional[str] = Header(default=None)):
    payload = _decode_bearer(authorization)
    sender_email = str(payload.get("sub", "")).lower()
    if not sender_email or sender_email not in users:
        raise HTTPException(status_code=401, detail="Invalid user.")

    message = _send_message(sender_email, request.to_email, request.text)
    recipient = message["recipient"]

    recipient_socket = ws_connections.get(recipient)
    if recipient_socket:
        await recipient_socket.send_json({"type": "new_message", "message": message})

    return {"message": message}


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
                if isinstance(lat, (int, float)):
                    user["lat"] = float(lat)
                if isinstance(lng, (int, float)):
                    user["lng"] = float(lng)
                user["last_seen_at"] = datetime.now(tz=timezone.utc).isoformat()
                users[email] = user
                _save_users()

                await websocket.send_json(_build_match_payload(email, from_currency, to_currency))
            elif message_type == "send_message":
                to_email = str(raw.get("toEmail", "")).lower()
                text = str(raw.get("text", ""))
                try:
                    message = _send_message(email, to_email, text)
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "message": exc.detail})
                    continue

                await websocket.send_json({"type": "message_sent", "message": message})
                recipient_socket = ws_connections.get(to_email)
                if recipient_socket:
                    await recipient_socket.send_json({"type": "new_message", "message": message})
            else:
                await websocket.send_json({"type": "error", "message": "Unsupported event type."})
    except WebSocketDisconnect:
        pass
    finally:
        if ws_connections.get(email) is websocket:
            ws_connections.pop(email, None)


_load_state()
