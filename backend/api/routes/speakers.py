"""
Speaker management endpoints
"""

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile
import os

from services.stt_service import stt_service

router = APIRouter()


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

