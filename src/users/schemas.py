from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
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
    avatar_url: Optional[str] = None
    is_following: bool = False

    class Config:
        from_attributes = True
