from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# Import routers
from src.auth import router as auth_router
from src.middleware.error_handler import general_exception_handler
from src.posts import router as posts_router
from src.spotify import router as spotify_router
from src.storage import router as storage_router
from src.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("🚀 Starting AUX App Backend...")
    print(f"📝 Environment: {settings.ENVIRONMENT}")
    print(f"🔗 API Prefix: {settings.API_V1_PREFIX}")
    yield
    # Shutdown
    print("👋 Shutting down AUX App Backend...")


# Create FastAPI app
app = FastAPI(
    title="AUX App API",
    description="Backend API for AUX - A music social network powered by Spotify",
    version="1.0.0",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(Exception, general_exception_handler)

# Register routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(posts_router, prefix=settings.API_V1_PREFIX)
app.include_router(spotify_router, prefix=settings.API_V1_PREFIX)
app.include_router(storage_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to AUX App API",
        "version": "1.0.0",
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
    )
