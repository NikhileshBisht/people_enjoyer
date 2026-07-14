"""
enjoyer/router.py
FastAPI router for enjoyer profile endpoints.

Endpoints
---------
POST   /enjoyer/profile          Create or update a profile + 4 photos (multipart/form-data)
GET    /enjoyer/profile/{id}     Fetch a profile and its ordered photo URLs
"""
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from . import service

router = APIRouter(prefix="/enjoyer", tags=["enjoyer"])


@router.post("/profile", summary="Create or update an enjoyer profile")
async def create_profile(
    name: str = Form(..., description="Display name"),
    age: int = Form(..., ge=1, le=120, description="Age (1-120)"),
    bio: Optional[str] = Form(None, description="Short biography"),
    photos: List[UploadFile] = File(..., description="Exactly 4 photos"),
    profile_id: int = Form(0, description="Existing profile ID to update; 0 = create new"),
):
    """
    Accept multipart/form-data from the ProfilePopup component.

    Form fields
    -----------
    - name        : str
    - age         : int
    - bio         : str (optional)
    - photos      : 4 image files (jpeg / png / webp / gif, max 5 MB each)
    - profile_id  : int  (0 → create new row; >0 → update existing)

    Returns the saved profile including ordered photo URLs.
    """
    result = await service.create_or_update_profile(
        user_row_id=profile_id,
        name=name,
        age=age,
        bio=bio,
        photos=photos,
    )
    return {"profile": result}


@router.get("/profile/{profile_id}", summary="Get an enjoyer profile by ID")
def get_profile(profile_id: int):
    """Return the profile row and its ordered photo URLs."""
    return {"profile": service.get_profile(profile_id)}
