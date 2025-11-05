from datetime import datetime, timedelta
from typing import List

import spotipy
from fastapi import APIRouter, Depends, HTTPException, Query, status
from spotipy.oauth2 import SpotifyOAuth
from supabase._sync.client import SyncClient as Client

from config.settings import settings
from src.middleware import get_current_user, get_supabase_client

from .schemas import (
    CurrentlyPlaying,
    SpotifyAuthResponse,
    SpotifyCallbackRequest,
    SpotifyConnectionStatus,
    SpotifyPlaylist,
    SpotifySearchResponse,
    SpotifyTrack,
)

router = APIRouter(prefix="/spotify", tags=["Spotify"])


def get_spotify_oauth() -> SpotifyOAuth:
    """Get Spotify OAuth handler."""
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state user-read-currently-playing user-top-read playlist-read-private",
    )


def get_user_spotify_client(user: dict) -> spotipy.Spotify:
    """Get Spotify client for a user with valid tokens."""
    if not user.get("spotify_access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Spotify not connected"
        )

    # Check if token is expired
    expires_at = user.get("spotify_token_expires_at")
    if expires_at:
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires_at <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Spotify token expired, please reconnect",
            )

    token_info = {
        "access_token": user["spotify_access_token"],
        "refresh_token": user["spotify_refresh_token"],
        "expires_at": int(expires_at.timestamp()) if expires_at else 0,
    }

    return spotipy.Spotify(auth=token_info["access_token"])


@router.get("/connect", response_model=SpotifyAuthResponse)
async def connect_spotify(current_user: dict = Depends(get_current_user)):
    """Get Spotify authorization URL."""
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()

    return SpotifyAuthResponse(auth_url=auth_url)


@router.post("/callback", response_model=SpotifyConnectionStatus)
async def spotify_callback(
    callback_data: SpotifyCallbackRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Handle Spotify OAuth callback and save tokens."""
    sp_oauth = get_spotify_oauth()

    try:
        token_info = sp_oauth.get_access_token(callback_data.code, check_cache=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get access token: {str(e)}",
        )

    # Get Spotify user info
    sp = spotipy.Spotify(auth=token_info["access_token"])
    spotify_user = sp.current_user()

    if not spotify_user or "id" not in spotify_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Spotify user info",
        )

    # Calculate token expiration
    expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

    # Update user with Spotify tokens
    update_data = {
        "spotify_access_token": token_info["access_token"],
        "spotify_refresh_token": token_info["refresh_token"],
        "spotify_token_expires_at": expires_at.isoformat(),
    }

    supabase.table("users").update(update_data).eq("id", current_user["id"]).execute()

    return SpotifyConnectionStatus(connected=True)


@router.delete("/disconnect", response_model=SpotifyConnectionStatus)
async def disconnect_spotify(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Disconnect Spotify account."""
    update_data = {
        "spotify_access_token": None,
        "spotify_refresh_token": None,
        "spotify_token_expires_at": None,
    }

    supabase.table("users").update(update_data).eq("id", current_user["id"]).execute()

    return SpotifyConnectionStatus(connected=False)


@router.get("/status", response_model=SpotifyConnectionStatus)
async def get_spotify_status(current_user: dict = Depends(get_current_user)):
    """Get Spotify connection status."""
    return SpotifyConnectionStatus(
        connected=bool(current_user.get("spotify_access_token"))
    )


@router.get("/search", response_model=SpotifySearchResponse)
async def search_tracks(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Search for tracks on Spotify."""
    sp_client = get_user_spotify_client(current_user)

    try:
        results = sp_client.search(q=q, type="track", limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spotify API error: {str(e)}",
        )

    if not results or "tracks" not in results or "items" not in results["tracks"]:
        return SpotifySearchResponse(tracks=[])

    tracks = []
    for item in results["tracks"]["items"]:
        track = SpotifyTrack(
            id=item.get("id", ""),
            name=item.get("name", ""),
            artists=[artist["name"] for artist in item.get("artists", [])],
            album=item.get("album", {}).get("name", ""),
            album_art=(
                item.get("album", {}).get("images", [{}])[0].get("url")
                if item.get("album", {}).get("images")
                else None
            ),
            preview_url=item.get("preview_url"),
            duration_ms=item.get("duration_ms", 0),
            uri=item.get("uri", ""),
        )
        tracks.append(track)

    return SpotifySearchResponse(tracks=tracks)


@router.get("/track/{track_id}", response_model=SpotifyTrack)
async def get_track(track_id: str, current_user: dict = Depends(get_current_user)):
    """Get track details by ID."""
    sp_client = get_user_spotify_client(current_user)

    try:
        item = sp_client.track(track_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Track not found: {str(e)}"
        )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
        )

    return SpotifyTrack(
        id=item["id"],
        name=item["name"],
        artists=[artist["name"] for artist in item.get("artists", [])],
        album=item.get("album", {}).get("name", ""),
        album_art=(
            item.get("album", {}).get("images", [{}])[0].get("url")
            if item.get("album", {}).get("images")
            else None
        ),
        preview_url=item.get("preview_url"),
        duration_ms=item.get("duration_ms", 0),
        uri=item.get("uri", ""),
    )


@router.get("/playlists", response_model=List[SpotifyPlaylist])
async def get_user_playlists(
    limit: int = Query(20, ge=1, le=50), current_user: dict = Depends(get_current_user)
):
    """Get user's Spotify playlists."""
    sp_client = get_user_spotify_client(current_user)

    try:
        results = sp_client.current_user_playlists(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spotify API error: {str(e)}",
        )

    if not results or "items" not in results:
        return []

    playlists = []
    for item in results["items"]:
        playlist = SpotifyPlaylist(
            id=item["id"],
            name=item["name"],
            description=item.get("description"),
            image=item.get("images", [{}])[0].get("url") if item.get("images") else None,
            tracks_total=item.get("tracks", {}).get("total", 0),
        )
        playlists.append(playlist)

    return playlists


@router.get("/currently-playing", response_model=CurrentlyPlaying)
async def get_currently_playing(current_user: dict = Depends(get_current_user)):
    """Get user's currently playing track."""
    sp_client = get_user_spotify_client(current_user)

    try:
        current = sp_client.current_playback()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spotify API error: {str(e)}",
        )

    if not current or not current.get("item"):
        return CurrentlyPlaying(is_playing=False)

    item = current.get("item")
    if not item:
        return CurrentlyPlaying(is_playing=False)

    track = SpotifyTrack(
        id=item.get("id", ""),
        name=item.get("name", ""),
        artists=[artist["name"] for artist in item.get("artists", [])],
        album=item.get("album", {}).get("name", ""),
        album_art=(
            item.get("album", {}).get("images", [{}])[0].get("url")
            if item.get("album", {}).get("images")
            else None
        ),
        preview_url=item.get("preview_url"),
        duration_ms=item.get("duration_ms", 0),
        uri=item.get("uri", ""),
    )

    return CurrentlyPlaying(
        track=track,
        is_playing=current.get("is_playing", False),
        progress_ms=current.get("progress_ms"),
    )


@router.get("/top-tracks", response_model=SpotifySearchResponse)
async def get_top_tracks(
    limit: int = Query(20, ge=1, le=50),
    time_range: str = Query(
        "medium_term", regex="^(short_term|medium_term|long_term)$"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's top tracks.
    time_range: short_term (4 weeks), medium_term (6 months), long_term (years)
    """
    sp_client = get_user_spotify_client(current_user)

    try:
        results = sp_client.current_user_top_tracks(limit=limit, time_range=time_range)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spotify API error: {str(e)}",
        )

    if not results or "items" not in results:
        return SpotifySearchResponse(tracks=[])

    tracks = []
    for item in results["items"]:
        track = SpotifyTrack(
            id=item.get("id", ""),
            name=item.get("name", ""),
            artists=[artist["name"] for artist in item.get("artists", [])],
            album=item.get("album", {}).get("name", ""),
            album_art=(
                item.get("album", {}).get("images", [{}])[0].get("url")
                if item.get("album", {}).get("images")
                else None
            ),
            preview_url=item.get("preview_url"),
            duration_ms=item.get("duration_ms", 0),
            uri=item.get("uri", ""),
        )
        tracks.append(track)

    return SpotifySearchResponse(tracks=tracks)
