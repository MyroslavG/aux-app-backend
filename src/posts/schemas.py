from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    spotify_track_id: str = Field(..., description="Spotify track ID")
    track_name: str = Field(..., min_length=1, max_length=255)
    artist_name: str = Field(..., min_length=1, max_length=255)
    album_name: Optional[str] = Field(None, max_length=255)
    album_art_url: Optional[str] = None
    caption: Optional[str] = Field(None, max_length=500)


class UpdatePostRequest(BaseModel):
    caption: Optional[str] = Field(None, max_length=500)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class CommentResponse(BaseModel):
    id: str
    user_id: str
    post_id: str
    content: str
    created_at: datetime
    user: "CommentUser"

    class Config:
        from_attributes = True


class CommentUser(BaseModel):
    id: str
    username: str
    display_name: str
    profile_image_url: Optional[str] = None


class PostAuthor(BaseModel):
    id: str
    username: str
    display_name: str
    profile_image_url: Optional[str] = None


class PostResponse(BaseModel):
    id: str
    user_id: str
    spotify_track_id: str
    track_name: str
    artist_name: str
    album_art_url: Optional[str] = None
    caption: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user: PostAuthor

    class Config:
        from_attributes = True


class LikeResponse(BaseModel):
    is_liked: bool
    likes_count: int
