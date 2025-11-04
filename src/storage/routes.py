import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from supabase._sync.client import SyncClient as Client

from config.settings import settings
from src.middleware import get_current_user, get_supabase_client

from .schemas import DeleteRequest, UploadResponse

router = APIRouter(prefix="/storage", tags=["Storage"])


ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_image(file: UploadFile) -> None:
    """Validate image file."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )


def optimize_image(image_bytes: bytes, max_width: int = 1200) -> bytes:
    """Optimize image by resizing and compressing."""
    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA to RGB if necessary
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, "white")  # type: ignore
        background.paste(img, mask=img.split()[3])
        img = background

    # Resize if too large
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # Save optimized image
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()


@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Upload an image file to Supabase storage."""
    validate_image(file)

    # Read file
    file_bytes = await file.read()

    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image too large. Maximum size: {MAX_IMAGE_SIZE / 1024 / 1024}MB",
        )

    # Optimize image
    try:
        optimized_bytes = optimize_image(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process image: {str(e)}",
        )

    # Generate unique filename
    file_ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    file_name = f"{current_user['id']}/{uuid.uuid4()}{file_ext}"

    # Upload to Supabase storage
    try:
        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET_IMAGES).upload(
            file_name, optimized_bytes, {"contentType": "image/jpeg"}  # type: ignore
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}",
        )

    # Get public URL
    file_url = supabase.storage.from_(
        settings.SUPABASE_STORAGE_BUCKET_IMAGES
    ).get_public_url(file_name)

    return UploadResponse(
        file_url=file_url,
        file_path=file_name,
        bucket=settings.SUPABASE_STORAGE_BUCKET_IMAGES,
    )


@router.delete("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    delete_data: DeleteRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
):
    """Delete an image file from storage."""
    # Check if file belongs to user
    if not delete_data.file_path.startswith(f"{current_user['id']}/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this file",
        )

    # Delete from images bucket
    try:
        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET_IMAGES).remove(
            [delete_data.file_path]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}",
        )

    return None
