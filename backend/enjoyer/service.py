"""
enjoyer/service.py
Business logic for creating / fetching enjoyer profiles.

Flow for POST /enjoyer/profile (multipart):
  1. Upsert a row in public.user_enjoyer  (name, age, bio)
  2. Upload each photo to Supabase Storage bucket 'enjoyer-photos'
  3. Insert rows into public.user_enjoyer_photos (photo_url, photo_order)
  4. Return the full profile with ordered photo URLs
"""
from __future__ import annotations

import mimetypes
import uuid
from typing import List

from fastapi import HTTPException, UploadFile

from db import supabase

# Supabase Storage bucket name — create this in the Supabase dashboard
# (Storage → New bucket → "enjoyer-photos", public read)
BUCKET = "enjoyer-photos"

# Maximum allowed photo file size: 5 MB
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _upsert_profile(profile_id: int, name: str, age: int, bio: str | None) -> dict:
    """Insert or update a row in user_enjoyer and return the record."""
    if profile_id > 0:
        existing = (
            supabase.table("user_enjoyer")
            .select("id")
            .eq("id", profile_id)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Profile not found.")

        res = (
            supabase.table("user_enjoyer")
            .update({"name": name, "age": age, "bio": bio, "updated_at": "now()"})
            .eq("id", profile_id)
            .execute()
        )
    else:
        res = (
            supabase.table("user_enjoyer")
            .insert({"name": name, "age": age, "bio": bio})
            .execute()
        )

    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to save profile.")
    return res.data[0]


def _upload_photo(file_bytes: bytes, content_type: str, user_row_id: int, order: int) -> str:
    """Upload a single photo to Supabase Storage and return its public URL."""
    ext = mimetypes.guess_extension(content_type) or ".jpg"
    # normalise .jpeg → .jpg
    if ext == ".jpeg":
        ext = ".jpg"
    object_path = f"{user_row_id}/{uuid.uuid4().hex}{ext}"

    supabase.storage.from_(BUCKET).upload(
        path=object_path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )

    url_res = supabase.storage.from_(BUCKET).get_public_url(object_path)
    return url_res  # returns the public URL string


def _delete_existing_photos(user_row_id: int) -> None:
    """Remove old photo rows (and storage objects) before re-uploading."""
    res = (
        supabase.table("user_enjoyer_photos")
        .select("photo_url")
        .eq("user_id", user_row_id)
        .execute()
    )
    old_rows = res.data or []

    # Delete storage objects
    old_paths = []
    for row in old_rows:
        url: str = row["photo_url"]
        # Extract the object path after the bucket name segment
        marker = f"/{BUCKET}/"
        idx = url.find(marker)
        if idx != -1:
            old_paths.append(url[idx + len(marker):])
    if old_paths:
        supabase.storage.from_(BUCKET).remove(old_paths)

    # Delete DB rows
    supabase.table("user_enjoyer_photos").delete().eq("user_id", user_row_id).execute()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_or_update_profile(
    user_row_id: int,   # 0 = create new; >0 = update existing
    name: str,
    age: int,
    bio: str | None,
    photos: List[UploadFile],
) -> dict:
    """
    Validate inputs, upsert the profile row, upload photos, persist URLs.
    Returns a dict with keys: id, name, age, bio, photos (list of urls).
    """
    # ---- Validation ----
    if not name or not name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")
    if age < 1 or age > 120:
        raise HTTPException(status_code=422, detail="Age must be between 1 and 120.")
    if len(photos) != 4:
        raise HTTPException(status_code=422, detail="Exactly 4 photos are required.")

    photo_bytes_list: list[tuple[bytes, str]] = []
    for photo in photos:
        content_type = photo.content_type or "image/jpeg"
        if content_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported image type '{content_type}'. Allowed: jpeg, png, webp, gif.",
            )
        raw = await photo.read()
        if len(raw) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=422, detail=f"Each photo must be under 5 MB.")
        photo_bytes_list.append((raw, content_type))

    # ---- Upsert profile ----
    profile_row = _upsert_profile(user_row_id, name.strip(), age, bio)
    actual_id: int = profile_row["id"]

    # ---- Delete old photos (for update flow) ----
    if user_row_id > 0:
        _delete_existing_photos(actual_id)

    # ---- Upload new photos & persist URLs ----
    photo_rows = []
    urls: list[str] = []
    for order, (raw, ct) in enumerate(photo_bytes_list):
        url = _upload_photo(raw, ct, actual_id, order)
        urls.append(url)
        photo_rows.append({
            "user_id": actual_id,
            "photo_url": url,
            "photo_order": order,
        })

    supabase.table("user_enjoyer_photos").insert(photo_rows).execute()

    return {
        "id": actual_id,
        "name": profile_row["name"],
        "age": profile_row["age"],
        "bio": profile_row.get("bio"),
        "is_deactivated": profile_row.get("is_deactivated", False),
        "photos": urls,
        "created_at": str(profile_row.get("created_at", "")),
        "updated_at": str(profile_row.get("updated_at", "")),
    }


def get_profile(user_row_id: int) -> dict:
    """Fetch a profile and its ordered photos from Supabase."""
    profile = (
        supabase.table("user_enjoyer")
        .select("*")
        .eq("id", user_row_id)
        .execute()
    )
    if not profile.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    row = profile.data[0]

    photos_res = (
        supabase.table("user_enjoyer_photos")
        .select("photo_url")
        .eq("user_id", user_row_id)
        .order("photo_order")
        .execute()
    )
    urls = [r["photo_url"] for r in (photos_res.data or [])]

    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "bio": row.get("bio"),
        "is_deactivated": row.get("is_deactivated", False),
        "photos": urls,
        "created_at": str(row.get("created_at", "")),
        "updated_at": str(row.get("updated_at", "")),
    }
