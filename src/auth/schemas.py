from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(..., description="Google ID token from client")


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    spotify_connected: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
