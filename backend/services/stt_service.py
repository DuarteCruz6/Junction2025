"""
Speech-to-Text Service
Handles audio transcription and speaker diarization using OpenAI
"""

import os
from typing import List, Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import base64

load_dotenv()

class STTService:
    """Service for speech-to-text transcription with speaker diarization"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.known_speakers: Dict[str, str] = {}  # speaker_name -> audio_file_path
        self.speaker_references: Dict[str, str] = {}  # speaker_name -> data_url
        
    def register_speaker(self, name: str, audio_file_path: str):
        """Register a known speaker with their voice sample"""
        self.known_speakers[name] = audio_file_path
        self.speaker_references[name] = self._to_data_url(audio_file_path)
        
    def _to_data_url(self, path: str) -> str:
        """Convert audio file to data URL format"""
        with open(path, "rb") as fh:
            return "data:audio/wav;base64," + base64.b64encode(fh.read()).decode("utf-8")
    
    async def transcribe_with_diarization(
        self,
        audio_data: bytes,
        audio_format: str = "m4a",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio with speaker diarization
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (m4a, wav, mp3, etc.)
            language: Optional language code (e.g., 'en', 'pt')
            
        Returns:
            Dict with transcript segments, each containing:
            - speaker: Speaker identifier
            - text: Transcribed text
            - start: Start time in seconds
            - end: End time in seconds
        """
        try:
            # Save audio to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as tmp_file:
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name
            
            try:
                # Prepare extra body for known speakers
                extra_body = {}
                if self.known_speakers:
                    extra_body = {
                        "known_speaker_names": list(self.known_speakers.keys()),
                        "known_speaker_references": [
                            self.speaker_references[name] 
                            for name in self.known_speakers.keys()
                        ],
                    }
                
                # Transcribe with diarization
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="gpt-4o-transcribe-diarize",
                        file=audio_file,
                        response_format="diarized_json",
                        chunking_strategy="auto",
                        language=language,
                        **({"extra_body": extra_body} if extra_body else {})
                    )
                
                # Format response
                segments = []
                for segment in transcript.segments:
                    segments.append({
                        "speaker": segment.speaker or "Unknown",
                        "text": segment.text,
                        "start": segment.start,
                        "end": segment.end,
                    })
                
                return {
                    "success": True,
                    "segments": segments,
                    "full_text": " ".join([s["text"] for s in segments]),
                }
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "full_text": "",
            }
    
    async def transcribe_streaming(
        self,
        audio_chunk: bytes,
        meeting_id: str,
        is_final: bool = False
    ) -> Dict[str, Any]:
        """
        Process streaming audio chunk (for real-time transcription)
        
        Note: OpenAI's API doesn't support true streaming diarization yet,
        so this buffers chunks and processes them periodically.
        """
        # For now, return placeholder
        # In production, you'd buffer chunks and process every 2-3 seconds
        return {
            "success": True,
            "text": "[Streaming transcription - buffer and process periodically]",
            "speaker": "Unknown",
            "is_final": is_final,
        }


# Singleton instance
stt_service = STTService()

