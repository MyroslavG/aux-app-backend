from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    display_name: Optional[str] = Field(None, min_length=1, max_length=50)
    bio: Optional[str] = Field(None, max_length=100)
    profile_image_url: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        # Check if username contains only lowercase letters, numbers, and underscores
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain lowercase letters, numbers, underscores, and hyphens")

        # Check if username contains uppercase letters
        if v != v.lower():
            raise ValueError("Username must be lowercase")

        # Check if username starts with a letter
        if not v[0].isalpha():
            raise ValueError("Username must start with a letter")

        return v


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    spotify_connected: bool = False
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_following: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class FollowResponse(BaseModel):
    is_following: bool
    followers_count: int


class UserSearchResult(BaseModel):
    id: str
    username: str
    display_name: str
    profile_image_url: Optional[str] = None
    is_following: bool = False

    class Config:
        from_attributes = True
