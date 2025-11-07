from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase._sync.client import SyncClient as Client

from src.middleware import get_current_user, get_supabase_client

from .schemas import MarkAsReadRequest, NotificationResponse, UnreadCountResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False, description="Only return unread notifications"),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get notifications for the current user."""
    query = (
        supabase.table("notifications")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if unread_only:
        query = query.eq("is_read", False)

    result = query.execute()

    return [NotificationResponse(**notification) for notification in result.data]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get count of unread notifications."""
    result = (
        supabase.table("notifications")
        .select("id", count="exact")  # type: ignore
        .eq("user_id", current_user["id"])
        .eq("is_read", False)
        .execute()
    )

    return UnreadCountResponse(unread_count=result.count or 0)


@router.post("/mark-as-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_as_read(
    request: MarkAsReadRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Mark multiple notifications as read."""
    # Update notifications
    result = (
        supabase.table("notifications")
        .update({"is_read": True})
        .eq("user_id", current_user["id"])
        .in_("id", request.notification_ids)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No notifications found to mark as read",
        )

    return None


@router.post("/mark-all-as-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Mark all notifications as read for the current user."""
    supabase.table("notifications").update({"is_read": True}).eq(
        "user_id", current_user["id"]
    ).eq("is_read", False).execute()

    return None


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Delete a specific notification."""
    result = (
        supabase.table("notifications")
        .delete()
        .eq("id", notification_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or you don't have permission to delete it",
        )

    return None
