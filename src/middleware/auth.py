from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from supabase._sync.client import SyncClient as Client
from supabase._sync.client import create_client

from config.settings import settings

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_supabase_client() -> Client:
    """Create and return a Supabase client."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with longer expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    # Refresh tokens last 90 days
    expire = now + timedelta(days=90)

    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Get the current authenticated user from JWT token."""
    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("sub")
    if user_id is None or not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    response = supabase.table("users").select("*").eq("id", user_id).single().execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = response.data
    # Derive spotify_connected from whether spotify_access_token exists
    user_data["spotify_connected"] = bool(user_data.get("spotify_access_token"))

    return user_data


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
    supabase: Client = Depends(get_supabase_client),
) -> Optional[dict]:
    """Get the current user if authenticated, otherwise return None."""
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, supabase)
    except HTTPException:
        return None
