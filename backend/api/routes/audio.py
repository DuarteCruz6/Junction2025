"""
Audio streaming and STT endpoints
"""

from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from services.stt_service import stt_service
from services.websocket_manager import websocket_manager
from services.translation_service import translation_service
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db

router = APIRouter()


class TranscriptionSegment(BaseModel):
    """Transcription segment from Lens Studio ASR"""
    text: str
    speaker: Optional[str] = "Unknown"
    start: Optional[float] = None
    end: Optional[float] = None
    is_final: bool = False


class TranscriptionRequest(BaseModel):
    """Request body for transcription submission"""
    segments: List[TranscriptionSegment]


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
    
    # Process each segment (translate BEFORE showing)
    new_segments = []
    target_language = translation_service.get_target_language_for_user(None)
    
    for segment in result["segments"]:
        text = segment["text"]
        
        # Translate if needed BEFORE creating caption
        display_text = text  # Default to original
        try:
            translation_result = await translation_service.translate_text(
                text=text,
                target_language=target_language
            )
            if translation_result.get("success") and translation_result.get("translation_needed"):
                display_text = translation_result.get("translated_text", text)
                print(f"🌐 Translation: {text[:50]}... → {display_text[:50]}...", flush=True)
        except Exception as e:
            print(f"[Audio] ⚠️  Translation error (using original text): {e}", flush=True)
            # Use original text if translation fails
        
        # Create transcript entry with final translated text
        transcript_entry = {
            "text": text,  # Original text (always preserve)
            "translated_text": display_text,  # Text to display (translated or original)
            "speaker": segment["speaker"],
            "start": segment["start"],
            "end": segment["end"],
            "timestamp": datetime.now().isoformat(),
        }
        
        meeting["transcript"].append(transcript_entry)
        new_segments.append(transcript_entry)
        
        # Broadcast transcript update (with final text)
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


@router.post("/api/transcriptions/{meeting_id}")
async def submit_transcription(
    meeting_id: str,
    request: TranscriptionRequest,
):
    """Receive transcriptions from Lens Studio ASR API"""
    print(f"[Backend] Received transcription request for meeting {meeting_id}")
    print(f"[Backend] Segments count: {len(request.segments)}")
    
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        print(f"[Backend] ERROR: Meeting {meeting_id} not found")
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    if meeting.get("status") != "active":
        print(f"[Backend] ERROR: Meeting {meeting_id} is not active (status: {meeting.get('status')})")
        raise HTTPException(status_code=400, detail="Meeting is not active")
    
    print(f"[Backend] Meeting {meeting_id} is active, processing transcriptions...")
    
    # Process each transcription segment
    new_segments = []
    current_time = datetime.now()
    
    for segment in request.segments:
        # Calculate timing if not provided
        # For Lens Studio ASR, we approximate timing based on text length
        # Average speaking rate is ~150 words per minute = 2.5 words per second
        if segment.start is None or segment.end is None:
            word_count = len(segment.text.split())
            estimated_duration = word_count / 2.5  # seconds
            
            # Use last segment's end time or current time
            if meeting["transcript"]:
                last_entry = meeting["transcript"][-1]
                start_time = last_entry.get("end", 0.0)
            else:
                # First segment - calculate from meeting start
                start_dt = datetime.fromisoformat(meeting["start_time"])
                start_time = (current_time - start_dt).total_seconds()
            
            end_time = start_time + estimated_duration
        else:
            start_time = segment.start
            end_time = segment.end
        
        # Translate if needed BEFORE creating caption
        target_language = translation_service.get_target_language_for_user(None)
        display_text = segment.text  # Default to original
        
        try:
            translation_result = await translation_service.translate_text(
                text=segment.text,
                target_language=target_language
            )
            if translation_result.get("success") and translation_result.get("translation_needed"):
                display_text = translation_result.get("translated_text", segment.text)
                print(f"🌐 Translation: {segment.text[:50]}... → {display_text[:50]}...", flush=True)
        except Exception as e:
            print(f"[Audio] ⚠️  Translation error (using original text): {e}", flush=True)
            # Use original text if translation fails
        
        # Create transcript entry with final translated text
        transcript_entry = {
            "text": segment.text,  # Original text (always preserve)
            "translated_text": display_text,  # Text to display (translated or original)
            "speaker": segment.speaker or "Unknown",
            "start": start_time,
            "end": end_time,
            "timestamp": current_time.isoformat(),
        }
        
        meeting["transcript"].append(transcript_entry)
        new_segments.append(transcript_entry)
        
        # Show transcription
        speaker = segment.speaker or "Unknown"
        print(f"📝 {speaker}: {display_text}")
        
        # Broadcast transcript update (with final text)
        await websocket_manager.send_transcript_update(
            meeting_id=meeting_id,
            transcript_entry=transcript_entry
        )
    
    # Save updated meeting to database
    save_meeting_to_db(meeting)
    
    return JSONResponse(content={
        "success": True,
        "segments_added": len(new_segments),
        "segments": new_segments,
    })

