from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class MarkAsReadRequest(BaseModel):
    notification_ids: list[str] = Field(..., min_length=1)


class UnreadCountResponse(BaseModel):
    unread_count: int
