"""
Meeting management endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid
import asyncio

from services.llm_service import llm_service
from services.stt_service import stt_service
from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db, get_all_meetings_from_db, get_meeting_speakers, merge_diarized_transcripts
from utils.storage import meetings_db, audio_streams, background_tasks
from services.background_tasks import process_summary_update, process_task_extraction, process_batch_diarization

router = APIRouter()


@router.post("/api/meetings/start")
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
    
    # Save to database
    save_meeting_to_db(meeting_data)
    audio_streams[meeting_id] = []
    
    # Start background tasks
    print(f"[Meetings API] 🚀 Starting background tasks for meeting {meeting_id}", flush=True)
    summary_task = asyncio.create_task(process_summary_update(meeting_id))
    task_extraction_task = asyncio.create_task(process_task_extraction(meeting_id))
    batch_diarization_task = asyncio.create_task(process_batch_diarization(meeting_id))
    background_tasks[meeting_id] = {
        "summary": summary_task,
        "task_extraction": task_extraction_task,
        "batch_diarization": batch_diarization_task,
    }
    print(f"[Meetings API] ✅ Background tasks started for meeting {meeting_id}", flush=True)
    
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


@router.post("/api/meetings/{meeting_id}/stop")
async def stop_meeting(meeting_id: str):
    """Stop a meeting session and generate final summary"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting["status"] = "completed"
    meeting["end_time"] = datetime.now().isoformat()
    
    # Cancel background tasks
    if meeting_id in background_tasks:
        for task in background_tasks[meeting_id].values():
            task.cancel()
        del background_tasks[meeting_id]
    
    # Force process any remaining audio with diarization (before generating summary)
    print(f"[Meetings] 🔄 Processing remaining audio with diarization for meeting {meeting_id}...")
    diarization_result = await stt_service.process_batch_buffer_with_diarization(
        meeting_id=meeting_id,
        force=True  # Force process even if conditions aren't met
    )
    
    if diarization_result and diarization_result.get("success"):
        segments = diarization_result.get("segments", [])
        if segments:
            print(f"[Meetings] ✅ Processed {len(segments)} final segments with diarization")
            # Merge diarized results with existing transcripts
            merge_diarized_transcripts(meeting_id, segments)
    
    # Clear batch buffer
    stt_service.clear_batch_buffer(meeting_id)
    
    # Generate final summary if not exists
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
    
    # Save to database
    save_meeting_to_db(meeting)
    
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


@router.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get meeting details"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get speakers for this meeting
    speakers = get_meeting_speakers(meeting_id)
    
    # Add speakers to meeting response
    meeting_with_speakers = meeting.copy()
    meeting_with_speakers["speakers"] = speakers
    
    return JSONResponse(content=meeting_with_speakers)


@router.get("/api/meetings")
async def get_meetings():
    """Get all meetings (history)"""
    meetings = get_all_meetings_from_db()
    
    # Add speakers to each meeting
    for meeting in meetings:
        meeting_id = meeting.get("meeting_id")
        if meeting_id:
            speakers = get_meeting_speakers(meeting_id)
            meeting["speakers"] = speakers
    
    return JSONResponse(content={"meetings": meetings})


@router.get("/api/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    """Get current meeting summary (real-time updates)"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Trigger summary generation if not exists and we have transcript
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
            save_meeting_to_db(meeting)
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "summary": meeting.get("summary") or "Summary will be available shortly...",
        "last_updated": meeting.get("end_time") or meeting["start_time"],
    })


@router.get("/api/meetings/active")
async def get_active_meeting():
    """Get the current active meeting ID"""
    # Find active meeting in database
    try:
        from models.database import Meeting, SessionLocal
        if SessionLocal:
            db = SessionLocal()
            active_meeting = db.query(Meeting).filter(Meeting.status == "active").first()
            db.close()
            
            if active_meeting:
                return JSONResponse(content={
                    "meeting_id": active_meeting.id,
                    "status": "active",
                    "start_time": active_meeting.start_time.isoformat() if active_meeting.start_time else None,
                })
        
        # Fallback: check in-memory storage
        for meeting_id, meeting_data in meetings_db.items():
            if meeting_data.get("status") == "active":
                return JSONResponse(content={
                    "meeting_id": meeting_id,
                    "status": "active",
                    "start_time": meeting_data.get("start_time"),
                })
        
        return JSONResponse(content={"meeting_id": None, "status": "no_active_meeting"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active meeting: {str(e)}")


@router.get("/api/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(meeting_id: str):
    """Get meeting transcript"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "transcript": meeting.get("transcript", []),
    })

