"""
FastAPI Backend Application
Main entry point for the backend API
Enterprise Meeting AR - Spectacles Integration
"""

import sys
print("=" * 60)
print("🚀 Starting Junction2025 Backend...")
print("=" * 60)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

print("📦 Importing route routers...")
# Import route routers
from api.routes import health, meetings, audio, tasks, speakers, persons, settings
print("✅ Route routers imported")

# Import database initialization
try:
    from models.database import init_db
    DB_AVAILABLE = True
except Exception as e:
    print(f"Database not available: {e}. Using in-memory storage.")
    DB_AVAILABLE = False

load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Junction2025 Backend API",
    description="Backend API for Enterprise Meeting AR - Spectacles Integration",
    version="1.0.0",
)

# CORS middleware configuration - Allow all origins for Spectacles compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Spectacles/Lens Studio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database if available
if DB_AVAILABLE:
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")

# Include routers
app.include_router(health.router)
app.include_router(meetings.router)
app.include_router(audio.router)
app.include_router(tasks.router)
app.include_router(speakers.router)
app.include_router(persons.router)
app.include_router(settings.router)

# WebSocket routes need to be added directly (FastAPI routers don't support WebSocket)
print("📡 Importing WebSocket endpoints...")
from api.routes.websocket import websocket_endpoint, audio_streaming_endpoint
print("✅ WebSocket endpoints imported")
app.websocket("/ws/meetings/{meeting_id}")(websocket_endpoint)
app.websocket("/ws/audio/{meeting_id}")(audio_streaming_endpoint)
print("✅ WebSocket routes registered:")
print("   - /ws/meetings/{meeting_id}")
print("   - /ws/audio/{meeting_id}")
print("=" * 60)
print("✅ Backend initialization complete!")
print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
