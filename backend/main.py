"""
FastAPI Backend Application
Main entry point for the backend API
Enterprise Meeting AR - Spectacles Integration
"""

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List
from datetime import datetime
import uuid
import asyncio
import os
from dotenv import load_dotenv

# Import services
from services.stt_service import stt_service
from services.llm_service import llm_service
from services.websocket_manager import websocket_manager

# Import database (optional - can use in-memory for development)
try:
    from models.database import get_db, init_db, Meeting, Task
    DB_AVAILABLE = True
except Exception as e:
    print(f"Database not available: {e}. Using in-memory storage.")
    DB_AVAILABLE = False

load_dotenv()

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

# In-memory storage (fallback if DB not available)
meetings_db = {}
audio_streams = {}
tasks_db = {}

# Background task tracking
background_tasks = {}
summary_update_intervals = {}  # meeting_id -> asyncio.Task


# ==================== Background Processing ====================

async def process_summary_update(meeting_id: str):
    """Background task to periodically update meeting summary"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            
            # Only update if we have new transcript segments (at least 3)
            if len(transcript) >= 3:
                previous_summary = meeting.get("summary")
                
                # Generate summary using LLM
                result = await llm_service.summarize_meeting(
                    transcript=transcript,
                    previous_summary=previous_summary,
                    incremental=True
                )
                
                if result["success"]:
                    meeting["summary"] = result["summary"]
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_summary_update(
                        meeting_id=meeting_id,
                        summary=result["summary"]
                    )
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in summary update task for {meeting_id}: {e}")
            await asyncio.sleep(30)


async def process_task_extraction(meeting_id: str):
    """Background task to periodically extract tasks"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            existing_tasks = meeting.get("tasks", [])
            
            # Only extract if we have transcript segments
            if len(transcript) >= 5:  # Need some content to extract tasks
                result = await llm_service.extract_tasks(
                    transcript=transcript,
                    existing_tasks=existing_tasks
                )
                
                if result["success"] and result["tasks"]:
                    # Add new tasks
                    for task in result["tasks"]:
                        task_id = str(uuid.uuid4())
                        task_data = {
                            "task_id": task_id,
                            "description": task.get("description", ""),
                            "assignee": task.get("assignee"),
                            "due_date": task.get("due_date"),
                            "status": "pending",
                            "priority": task.get("priority", "medium"),
                            "created_at": datetime.now().isoformat(),
                        }
                        meeting["tasks"].append(task_data)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_tasks_update(
                        meeting_id=meeting_id,
                        tasks=meeting["tasks"]
                    )
            
            # Wait 60 seconds before next extraction
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Error in task extraction task for {meeting_id}: {e}")
            await asyncio.sleep(60)


# ==================== WebSocket Endpoints ====================

@app.websocket("/ws/meetings/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket, meeting_id)
    
    try:
        # Send initial state
        if meeting_id in meetings_db:
            meeting = meetings_db[meeting_id]
            await websocket_manager.send_personal_message({
                "type": "initial_state",
                "data": {
                    "meeting_id": meeting_id,
                    "status": meeting["status"],
                    "summary": meeting.get("summary"),
                    "tasks": meeting.get("tasks", []),
                    "transcript_count": len(meeting.get("transcript", [])),
                }
            }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming messages if needed
                # For now, just keep connection alive
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        print(f"WebSocket error for meeting {meeting_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, meeting_id)


# ==================== Root & Health ====================

@app.get("/")
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={"status": "healthy"})


# ==================== Meeting Endpoints ====================

@app.post("/api/meetings/start")
async def start_meeting():
    """Start a new meeting session"""
    meeting_id = str(uuid.uuid4())
    meeting_data = {
        "meeting_id": meeting_id,
        "start_time": datetime.now().isoformat(),
        "status": "active",
        "transcript": [],
        "summary": None,
        "tasks": [],
    }
    meetings_db[meeting_id] = meeting_data
    audio_streams[meeting_id] = []
    
    # Start background tasks
    summary_task = asyncio.create_task(process_summary_update(meeting_id))
    task_extraction_task = asyncio.create_task(process_task_extraction(meeting_id))
    background_tasks[meeting_id] = {
        "summary": summary_task,
        "task_extraction": task_extraction_task,
    }
    
    # Broadcast meeting started
    await websocket_manager.send_status_update(
        meeting_id=meeting_id,
        status="started",
        message="Meeting started"
    )
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "status": "started",
        "start_time": meeting_data["start_time"],
    })


@app.post("/api/meetings/{meeting_id}/stop")
async def stop_meeting(meeting_id: str):
    """Stop a meeting session and generate final summary"""
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = meetings_db[meeting_id]
    meeting["status"] = "completed"
    meeting["end_time"] = datetime.now().isoformat()
    
    # Cancel background tasks
    if meeting_id in background_tasks:
        for task in background_tasks[meeting_id].values():
            task.cancel()
        del background_tasks[meeting_id]
    
    # Generate final summary if not exists
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
    
    # Broadcast meeting ended
    await websocket_manager.send_status_update(
        meeting_id=meeting_id,
        status="completed",
        message="Meeting ended"
    )
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "status": "completed",
        "end_time": meeting["end_time"],
        "summary": meeting.get("summary"),
    })


@app.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get meeting details"""
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return JSONResponse(content=meetings_db[meeting_id])


@app.get("/api/meetings")
async def get_meetings():
    """Get all meetings (history)"""
    meetings = list(meetings_db.values())
    return JSONResponse(content={"meetings": meetings})


@app.get("/api/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    """Get current meeting summary (real-time updates)"""
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = meetings_db[meeting_id]
    
    # Trigger summary generation if not exists and we have transcript
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "summary": meeting.get("summary") or "Summary will be available shortly...",
        "last_updated": meeting.get("end_time") or meeting["start_time"],
    })


# ==================== Audio/STT Endpoints ====================

@app.post("/api/audio/stream")
async def stream_audio(
    file: UploadFile = File(...),
    x_meeting_id: Optional[str] = Header(None, alias="X-Meeting-ID"),
):
    """Receive audio stream for real-time STT processing"""
    if not x_meeting_id or x_meeting_id not in meetings_db:
        raise HTTPException(status_code=400, detail="Invalid or missing meeting ID")
    
    # Read audio data
    audio_data = await file.read()
    
    # Determine audio format from filename
    audio_format = "m4a"  # default
    if file.filename:
        ext = file.filename.split(".")[-1].lower()
        if ext in ["m4a", "wav", "mp3", "ogg", "flac"]:
            audio_format = ext
    
    # Process audio with STT service (OpenAI with diarization)
    result = await stt_service.transcribe_with_diarization(
        audio_data=audio_data,
        audio_format=audio_format,
        language=None  # Auto-detect
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"STT processing failed: {result.get('error', 'Unknown error')}"
        )
    
    # Process each segment
    meeting = meetings_db[x_meeting_id]
    new_segments = []
    
    for segment in result["segments"]:
        transcript_entry = {
            "text": segment["text"],
            "speaker": segment["speaker"],
            "start": segment["start"],
            "end": segment["end"],
            "timestamp": datetime.now().isoformat(),
        }
        
        meeting["transcript"].append(transcript_entry)
        new_segments.append(transcript_entry)
        
        # Broadcast transcript update via WebSocket
        await websocket_manager.send_transcript_update(
            meeting_id=x_meeting_id,
            transcript_entry=transcript_entry
        )
    
    # Return latest segment info
    if new_segments:
        latest = new_segments[-1]
        return JSONResponse(content={
            "transcript": latest["text"],
            "speaker": latest["speaker"],
            "full_text": result["full_text"],
            "segments": new_segments,
        })
    else:
        return JSONResponse(content={
            "transcript": "",
            "speaker": "Unknown",
            "full_text": "",
            "segments": [],
        })


# ==================== Tasks Endpoints ====================

@app.get("/api/meetings/{meeting_id}/tasks")
async def get_meeting_tasks(meeting_id: str):
    """Get extracted tasks from a meeting"""
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = meetings_db[meeting_id]
    tasks = meeting.get("tasks", [])
    
    return JSONResponse(content={"tasks": tasks})


@app.post("/api/meetings/{meeting_id}/tasks")
async def add_task(meeting_id: str, task: dict):
    """Manually add a task to a meeting"""
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "description": task.get("description", ""),
        "assignee": task.get("assignee"),
        "due_date": task.get("due_date"),
        "status": "pending",
        "priority": task.get("priority", "medium"),
        "created_at": datetime.now().isoformat(),
    }
    
    meeting = meetings_db[meeting_id]
    meeting["tasks"].append(task_data)
    
    # Broadcast task update
    await websocket_manager.send_tasks_update(
        meeting_id=meeting_id,
        tasks=meeting["tasks"]
    )
    
    return JSONResponse(content=task_data)


# ==================== Speaker Management ====================

@app.post("/api/speakers/register")
async def register_speaker(name: str, audio_file: UploadFile = File(...)):
    """Register a known speaker with their voice sample"""
    audio_data = await audio_file.read()
    
    # Save audio file temporarily
    import tempfile
    import os
    
    audio_format = "m4a"
    if audio_file.filename:
        ext = audio_file.filename.split(".")[-1].lower()
        if ext in ["m4a", "wav", "mp3", "ogg", "flac"]:
            audio_format = ext
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as tmp_file:
        tmp_file.write(audio_data)
        tmp_file_path = tmp_file.name
    
    try:
        # Register speaker with STT service
        stt_service.register_speaker(name, tmp_file_path)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Speaker '{name}' registered successfully",
        })
    finally:
        # Clean up temp file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


# ==================== Person Detection Endpoints ====================

@app.post("/api/persons/detect")
async def detect_person(image: UploadFile = File(...)):
    """Detect and identify person in image"""
    # TODO: Implement person detection and identification
    # person_id = await detect_and_identify_person(image)
    
    return JSONResponse(content={
        "person_id": None,
        "name": None,
        "confidence": 0.0,
        "is_known": False,
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
