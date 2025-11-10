from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase._sync.client import SyncClient as Client

from src.middleware import (
    get_current_user,
    get_optional_current_user,
    get_supabase_client,
)

from .schemas import CreatePostRequest, PostAuthor, PostResponse, UpdatePostRequest

router = APIRouter(prefix="/posts", tags=["Posts"])


class ExpirationCheckResponse(BaseModel):
    """Response for expiration check endpoint."""

    expired_count: int
    message: str


def format_post_with_user(post: dict, supabase: Client) -> PostResponse:
    """Format post data with user info."""
    # Get user info
    user = (
        supabase.table("users")
        .select("id, username, display_name, profile_image_url")
        .eq("id", post["user_id"])
        .single()
        .execute()
    )

    # Map database column names to response field names
    formatted_post = {
        "id": post["id"],
        "user_id": post["user_id"],
        "spotify_track_id": post["spotify_track_id"],
        "track_name": post["spotify_track_name"],
        "artist_name": post["spotify_artist_name"],
        "album_art_url": post.get("spotify_album_art_url"),
        "caption": post.get("caption"),
        "created_at": post["created_at"],
        "updated_at": post["updated_at"],
        "user": PostAuthor(**user.data),
    }

    return PostResponse(**formatted_post)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: CreatePostRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Create a new post with a Spotify track."""
    # Map CreatePostRequest fields to database column names
    new_post = {
        "user_id": current_user["id"],
        "spotify_track_id": post_data.spotify_track_id,
        "spotify_track_name": post_data.track_name,
        "spotify_artist_name": post_data.artist_name,
        "spotify_album_art_url": post_data.album_art_url,
        "caption": post_data.caption,
    }

    result = supabase.table("posts").insert(new_post).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create post",
        )

    post = result.data[0]
    return format_post_with_user(post, supabase)


@router.get("/feed", response_model=List[PostResponse])
async def get_feed(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Get personalized feed.
    If authenticated, shows posts from followed users + own posts.
    If not authenticated, shows recent posts.
    """
    current_user_id = current_user["id"] if current_user else None

    if current_user_id:
        # Get following IDs
        following = (
            supabase.table("follows")
            .select("following_id")
            .eq("follower_id", current_user_id)
            .execute()
        )

        following_ids = [f["following_id"] for f in following.data]
        following_ids.append(current_user_id)  # Include own posts

        # Get posts from followed users (exclude expired)
        posts = (
            supabase.table("posts")
            .select("*")
            .in_("user_id", following_ids)
            .eq("is_expired", False)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    else:
        # Get recent posts (exclude expired)
        posts = (
            supabase.table("posts")
            .select("*")
            .eq("is_expired", False)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    # Format posts with user info
    formatted_posts = [format_post_with_user(post, supabase) for post in posts.data]

    return formatted_posts


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get a specific post by ID."""
    post = (
        supabase.table("posts")
        .select("*")
        .eq("id", post_id)
        .eq("is_expired", False)
        .single()
        .execute()
    )

    if not post.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or has expired",
        )

    return format_post_with_user(post.data, supabase)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    update_data: UpdatePostRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Update a post (only caption can be updated)."""
    # Check if post exists and belongs to user
    post = (
        supabase.table("posts")
        .select("*")
        .eq("id", post_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )

    if not post.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or you don't have permission to edit it",
        )

    # Update post
    updated_post = (
        supabase.table("posts")
        .update(update_data.model_dump(exclude_unset=True))
        .eq("id", post_id)
        .execute()
    )

    if not updated_post.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update post",
        )

    return format_post_with_user(updated_post.data[0], supabase)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Delete a post."""
    # Check if post exists and belongs to user
    post = (
        supabase.table("posts")
        .select("id")
        .eq("id", post_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )

    if not post.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or you don't have permission to delete it",
        )

    # Delete post
    supabase.table("posts").delete().eq("id", post_id).execute()

    return None


@router.get("/user/{username}", response_model=List[PostResponse])
async def get_user_posts(
    username: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get posts by a specific user."""
    # Get user ID
    user = (
        supabase.table("users").select("id").eq("username", username).single().execute()
    )

    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get user's posts (exclude expired)
    posts = (
        supabase.table("posts")
        .select("*")
        .eq("user_id", user.data["id"])
        .eq("is_expired", False)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    # Format posts with user info
    formatted_posts = [format_post_with_user(post, supabase) for post in posts.data]

    return formatted_posts
