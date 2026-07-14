"""
enjoyer/schemas.py
Pydantic models for the enjoyer profile endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional


class EnjoyerProfileResponse(BaseModel):
    id: int
    name: str
    age: int
    bio: Optional[str]
    is_deactivated: bool
    photos: list[str]          # ordered list of photo_urls
    created_at: str
    updated_at: str
