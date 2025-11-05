from typing import List, Optional

from pydantic import BaseModel


class SpotifyAuthResponse(BaseModel):
    auth_url: str


class SpotifyCallbackRequest(BaseModel):
    code: str


class SpotifyConnectionStatus(BaseModel):
    connected: bool
    spotify_user_id: Optional[str] = None


class SpotifyTrack(BaseModel):
    id: str
    name: str
    artist: str  # Changed from artists: List[str] to match frontend
    album: str
    album_art_url: Optional[str] = None  # Changed from album_art to match frontend
    preview_url: Optional[str] = None
    duration_ms: int
    uri: str


class SpotifySearchResponse(BaseModel):
    tracks: List[SpotifyTrack]


class SpotifyPlaylist(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    tracks_total: int


class CurrentlyPlaying(BaseModel):
    track: Optional[SpotifyTrack] = None
    is_playing: bool
    progress_ms: Optional[int] = None
