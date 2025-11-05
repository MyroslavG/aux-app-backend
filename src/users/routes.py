from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase._sync.client import SyncClient as Client

from src.middleware import (
    get_current_user,
    get_optional_current_user,
    get_supabase_client,
)

from .schemas import FollowResponse, UserProfile, UserProfileUpdate, UserSearchResult

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_stats(user_id: str, supabase: Client) -> dict:
    """Get user statistics (followers, following, posts count)."""
    # Get followers count
    followers = (
        supabase.table("follows")
        .select("id", count="exact")  # type: ignore
        .eq("following_id", user_id)
        .execute()
    )

    # Get following count
    following = (
        supabase.table("follows")
        .select("id", count="exact")  # type: ignore
        .eq("follower_id", user_id)
        .execute()
    )

    # Get posts count
    posts = (
        supabase.table("posts")
        .select("id", count="exact")  # type: ignore
        .eq("user_id", user_id)
        .execute()
    )

    return {
        "followers_count": followers.count or 0,
        "following_count": following.count or 0,
        "posts_count": posts.count or 0,
    }


def check_if_following(follower_id: str, following_id: str, supabase: Client) -> bool:
    """Check if follower_id is following following_id."""
    if not follower_id:
        return False

    result = (
        supabase.table("follows")
        .select("id")
        .eq("follower_id", follower_id)
        .eq("following_id", following_id)
        .execute()
    )

    return len(result.data) > 0


@router.get("/search", response_model=List[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Search for users by username or display name."""
    search_query = f"%{q}%"

    # Search users
    users = (
        supabase.table("users")
        .select("id, username, display_name, profile_image_url")
        .or_(f"username.ilike.{search_query},display_name.ilike.{search_query}")
        .limit(limit)
        .execute()
    )

    # Add is_following status
    results = []
    current_user_id = current_user["id"] if current_user else None

    for user in users.data:
        is_following = (
            check_if_following(current_user_id, user["id"], supabase)
            if current_user_id
            else False
        )
        results.append(UserSearchResult(**user, is_following=is_following))

    return results


@router.get("/{username}", response_model=UserProfile)
async def get_user_profile(
    username: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get user profile by username."""
    # Get user
    user = (
        supabase.table("users")
        .select(
            "id, username, display_name, profile_image_url, bio, spotify_access_token, created_at"
        )
        .eq("username", username)
        .single()
        .execute()
    )

    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user_data = user.data
    # Derive spotify_connected from whether spotify_access_token exists
    user_data["spotify_connected"] = bool(user_data.get("spotify_access_token"))
    # Remove the token from response for security
    user_data.pop("spotify_access_token", None)

    stats = get_user_stats(user_data["id"], supabase)

    # Check if current user is following this user
    is_following = False
    if current_user and current_user["id"] != user_data["id"]:
        is_following = check_if_following(current_user["id"], user_data["id"], supabase)

    return UserProfile(**user_data, **stats, is_following=is_following)


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    update_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Update current user's profile."""
    # Prepare update data (only include fields that were provided)
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    # Update user
    updated_user = (
        supabase.table("users")
        .update(update_dict)
        .eq("id", current_user["id"])
        .execute()
    )

    if not updated_user.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        )

    user_data = updated_user.data[0]
    stats = get_user_stats(user_data["id"], supabase)

    return UserProfile(**user_data, **stats, is_following=False)


@router.post("/{username}/follow", response_model=FollowResponse)
async def follow_user(
    username: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Follow a user."""
    # Get target user
    target_user = (
        supabase.table("users").select("id").eq("username", username).single().execute()
    )

    if not target_user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    target_user_id = target_user.data["id"]

    # Can't follow yourself
    if target_user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself"
        )

    # Check if already following
    existing_follow = (
        supabase.table("follows")
        .select("id")
        .eq("follower_id", current_user["id"])
        .eq("following_id", target_user_id)
        .execute()
    )

    if existing_follow.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already following this user",
        )

    # Create follow
    supabase.table("follows").insert(
        {"follower_id": current_user["id"], "following_id": target_user_id}
    ).execute()

    # Get updated followers count
    followers = (
        supabase.table("follows")
        .select("id", count="exact")  # type: ignore
        .eq("following_id", target_user_id)
        .execute()
    )

    return FollowResponse(is_following=True, followers_count=followers.count or 0)


@router.delete("/{username}/follow", response_model=FollowResponse)
async def unfollow_user(
    username: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Unfollow a user."""
    # Get target user
    target_user = (
        supabase.table("users").select("id").eq("username", username).single().execute()
    )

    if not target_user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    target_user_id = target_user.data["id"]

    # Delete follow
    result = (
        supabase.table("follows")
        .delete()
        .eq("follower_id", current_user["id"])
        .eq("following_id", target_user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not following this user",
        )

    # Get updated followers count
    followers = (
        supabase.table("follows")
        .select("id", count="exact")  # type: ignore
        .eq("following_id", target_user_id)
        .execute()
    )

    return FollowResponse(is_following=False, followers_count=followers.count or 0)


@router.get("/{username}/followers", response_model=List[UserSearchResult])
async def get_followers(
    username: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get user's followers."""
    # Get user ID
    user = (
        supabase.table("users").select("id").eq("username", username).single().execute()
    )

    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get followers with user info
    followers = (
        supabase.table("follows")
        .select("follower:follower_id(id, username, display_name, profile_image_url)")
        .eq("following_id", user.data["id"])
        .range(offset, offset + limit - 1)
        .execute()
    )

    # Format results
    results = []
    current_user_id = current_user["id"] if current_user else None

    for follow in followers.data:
        follower = follow["follower"]
        is_following = (
            check_if_following(current_user_id, follower["id"], supabase)
            if current_user_id
            else False
        )
        results.append(UserSearchResult(**follower, is_following=is_following))

    return results


@router.get("/{username}/following", response_model=List[UserSearchResult])
async def get_following(
    username: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Get users that this user is following."""
    # Get user ID
    user = (
        supabase.table("users").select("id").eq("username", username).single().execute()
    )

    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get following with user info
    following = (
        supabase.table("follows")
        .select("following:following_id(id, username, display_name, profile_image_url)")
        .eq("follower_id", user.data["id"])
        .range(offset, offset + limit - 1)
        .execute()
    )

    # Format results
    results = []
    current_user_id = current_user["id"] if current_user else None

    for follow in following.data:
        following_user = follow["following"]
        is_following = (
            check_if_following(current_user_id, following_user["id"], supabase)
            if current_user_id
            else False
        )
        results.append(UserSearchResult(**following_user, is_following=is_following))

    return results
