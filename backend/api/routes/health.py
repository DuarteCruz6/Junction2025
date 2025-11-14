"""
Health check and root endpoints
"""

from fastapi.responses import JSONResponse
from fastapi import APIRouter

# Try to import DB_AVAILABLE from db_helpers
try:
    from utils.db_helpers import DB_AVAILABLE
except ImportError:
    DB_AVAILABLE = False

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse(
        content={
            "message": "Junction2025 Backend API",
            "status": "running",
            "version": "1.0.0",
            "features": {
                "stt": "OpenAI Whisper with Diarization",
                "llm": "GPT-4o-mini for Summarization & Task Extraction",
                "websocket": "Real-time updates enabled",
                "database": "Supabase/PostgreSQL" if DB_AVAILABLE else "Using in-memory storage",
            }
        }
    )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={"status": "healthy"})

