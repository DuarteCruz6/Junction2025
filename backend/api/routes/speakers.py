"""
Speaker management endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os

from services.stt_service import stt_service
from utils.db_helpers import get_meeting_speakers, get_meeting_from_db_or_memory, get_speaker_meetings, get_speaker_by_name

router = APIRouter()


@router.get("/api/meetings/{meeting_id}/speakers")
async def get_meeting_speakers_endpoint(meeting_id: str):
    """Get all speakers for a meeting"""
    # Verify meeting exists
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get speakers for this meeting
    speakers = get_meeting_speakers(meeting_id)
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "speakers": speakers,
        "count": len(speakers),
    })


@router.get("/api/speakers/{speaker_id}/meetings")
async def get_speaker_meetings_endpoint(speaker_id: str):
    """Get all meeting IDs for a speaker"""
    meeting_ids = get_speaker_meetings(speaker_id)
    
    return JSONResponse(content={
        "speaker_id": speaker_id,
        "meeting_ids": meeting_ids,
        "count": len(meeting_ids),
    })


@router.get("/api/speakers/by-name/{speaker_name}")
async def get_speaker_by_name_endpoint(speaker_name: str):
    """Get speaker by name with all their meetings"""
    speaker = get_speaker_by_name(speaker_name)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    
    # Get all meetings for this speaker
    meeting_ids = get_speaker_meetings(speaker["id"])
    
    return JSONResponse(content={
        **speaker,
        "meeting_ids": meeting_ids,
        "meeting_count": len(meeting_ids),
    })


@router.post("/api/speakers/register")
async def register_speaker(name: str, audio_file: UploadFile = File(...)):
    """Register a known speaker with their voice sample"""
    audio_data = await audio_file.read()
    
    # Save audio file temporarily
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

