from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token
from pydantic import BaseModel
from supabase._sync.client import SyncClient as Client

from config.settings import settings
from src.middleware.auth import (
    create_access_token,
    get_current_user,
    get_supabase_client,
)

router = APIRouter()


class GoogleSignInRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


@router.post("/google", response_model=AuthResponse)
async def google_sign_in(
    request: GoogleSignInRequest, supabase: Client = Depends(get_supabase_client)
):
    """Authenticate user with Google Sign-In ID token"""
    try:
        # Verify Google ID token
        idinfo = id_token.verify_oauth2_token(
            request.id_token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer"
            )

        google_id = idinfo["sub"]
        email = idinfo.get("email")
        name = idinfo.get("name", email.split("@")[0])
        picture = idinfo.get("picture")

        # Check if user exists
        user_response = (
            supabase.table("users").select("*").eq("google_id", google_id).execute()
        )

        if user_response.data:
            user = user_response.data[0]
        else:
            # Create new user
            username = email.split("@")[0] + "_" + google_id[:8]

            new_user = {
                "email": email,
                "google_id": google_id,
                "username": username,
                "display_name": name,
                "profile_image_url": picture,
            }

            user_response = supabase.table("users").insert(new_user).execute()

            if not user_response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user",
                )

            user = user_response.data[0]

        # Create JWT token
        access_token = create_access_token(data={"sub": str(user["id"])})

        return AuthResponse(access_token=access_token, token_type="bearer", user=user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}",
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user
