"""
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import settings
from app.api.routes import router, rag_service
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize RAG service
    if rag_service.initialize():
        logger.info("RAG service initialized successfully")
    else:
        logger.warning("RAG service not initialized - run ingestion first")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    AI-powered Developer Documentation Chatbot API.
    
    This API provides:
    - Documentation querying with RAG
    - Slack integration support
    - Conversation memory
    
    ## Endpoints
    
    - `/query` - Query documentation and get AI-generated answers
    - `/health` - Health check endpoint
    - `/slack/events` - Slack webhook handler
    - `/stats` - Service statistics
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# Serve frontend static files
import os

# Get the project root directory (parent of app folder)
project_root = Path(__file__).parent.parent.absolute()
frontend_path = project_root / "frontend"

print(f"Project root: {project_root}")
print(f"Frontend path: {frontend_path}")
print(f"Frontend exists: {frontend_path.exists()}")

if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/chat")
    async def chat():
        """Serve the chat interface."""
        return FileResponse(str(frontend_path / "index.html"))
    
    @app.get("/chat/")
    async def chat_slash():
        """Serve the chat interface (with trailing slash)."""
        return FileResponse(str(frontend_path / "index.html"))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
