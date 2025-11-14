"""
Audio streaming and STT endpoints
"""

from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime

from services.stt_service import stt_service
from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db

router = APIRouter()


@router.post("/api/audio/stream")
async def stream_audio(
    file: UploadFile = File(...),
    x_meeting_id: Optional[str] = Header(None, alias="X-Meeting-ID"),
):
    """Receive audio stream for real-time STT processing"""
    if not x_meeting_id:
        raise HTTPException(status_code=400, detail="Invalid or missing meeting ID")
    
    meeting = get_meeting_from_db_or_memory(x_meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Read audio data
    audio_data = await file.read()
    
    # Determine audio format from filename
    audio_format = "m4a"  # default
    if file.filename:
        ext = file.filename.split(".")[-1].lower()
        if ext in ["m4a", "wav", "mp3", "ogg", "flac"]:
            audio_format = ext
    
    # Process audio with STT service (ElevenLabs with diarization)
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
    
    # Save updated meeting to database
    save_meeting_to_db(meeting)
    
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

