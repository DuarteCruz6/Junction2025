"""
TTS Service
Handles text-to-speech conversion using ElevenLabs API
"""

import os
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

class TTSService:
    """Service for Text-to-Speech conversion using ElevenLabs"""
    
    # Bitmoji-style avatar generation
    # Using a service that generates unique Bitmoji-style avatars for each voice
    # In production, you could integrate with Bitmoji Kit API for user-specific avatars
    
    def __init__(self):
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("[TTS] ⚠️  WARNING: ELEVENLABS_API_KEY not found in environment variables", flush=True)
            self.client = None
        else:
            self.client = ElevenLabs(api_key=api_key)
        
        # Default voice ID (you can change this to a preferred voice)
        # Using a default voice - you can customize this
        self.default_voice_id = "JBFqnCBsd6RMkjVDRZzb"  # Default from ElevenLabs docs
        self.model_id = "eleven_multilingual_v2"
        self.output_format = "mp3_44100_128"
        
        # Create audio outputs directory if it doesn't exist
        self.audio_output_dir = Path(__file__).parent.parent / "audio_outputs"
        self.audio_output_dir.mkdir(exist_ok=True)
    
    def get_voice_bitmoji(self, voice_id: str) -> str:
        """Get Bitmoji URL for a voice ID"""
        # Generate a unique Bitmoji-style avatar for each voice using a hash-based approach
        # This creates consistent, unique avatars for each voice ID
        # Using DiceBear's avataaars style which creates Bitmoji-like avatars
        hash_value = int(hashlib.md5(voice_id.encode()).hexdigest(), 16)
        seed = str(hash_value % 1000000)  # Use hash as seed for consistent avatar
        
        # Using DiceBear Avataaars (Bitmoji-style) with unique seed per voice
        bitmoji_url = f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf"
        return bitmoji_url
    
    def get_voice_emoji(self, voice_id: str) -> str:
        """Get emoji for a voice ID (deprecated - use get_voice_bitmoji instead)"""
        # Keep for backward compatibility
        return "🎙️"
    
    def generate_audio(
        self,
        text: str,
        meeting_id: str,
        audio_type: str = "summary",  # "summary" or "transcript"
        voice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate audio from text and save to file
        
        Args:
            text: Text to convert to speech
            meeting_id: Meeting ID for file naming
            audio_type: Type of audio ("summary" or "transcript")
            voice_id: Optional voice ID (uses default if not provided)
            
        Returns:
            Dict with success status, file path, and error if any
        """
        try:
            if not self.client:
                error_msg = "ElevenLabs API client not initialized (missing ELEVENLABS_API_KEY)"
                print(f"[TTS] ❌ {error_msg}", flush=True)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": None,
                }
            
            if not text or not text.strip():
                error_msg = "Empty text - cannot generate audio"
                print(f"[TTS] ⚠️  {error_msg}", flush=True)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": None,
                }
            
            # Use provided voice_id or default
            voice = voice_id or self.default_voice_id
            
            print(f"[TTS] 🎙️  Generating {audio_type} audio for meeting {meeting_id}...", flush=True)
            print(f"[TTS] 📝 Text length: {len(text)} characters", flush=True)
            
            # Generate audio using ElevenLabs
            audio = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice,
                model_id=self.model_id,
                output_format=self.output_format,
            )
            
            # Save audio to file
            filename = f"{meeting_id}_{audio_type}.mp3"
            file_path = self.audio_output_dir / filename
            
            # Write audio bytes to file
            with open(file_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            
            print(f"[TTS] ✅ Audio saved to {file_path}", flush=True)
            
            return {
                "success": True,
                "file_path": str(file_path),
                "filename": filename,
                "relative_path": f"/audio/{filename}",
                "error": None,
            }
            
        except Exception as e:
            error_msg = f"Error generating audio: {str(e)}"
            print(f"[TTS] ❌ {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": error_msg,
                "file_path": None,
            }
    
    def generate_transcript_audio(
        self,
        transcript: list,
        meeting_id: str,
        voice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate audio from transcript segments
        
        Args:
            transcript: List of transcript segments with 'text' and 'speaker' fields
            meeting_id: Meeting ID for file naming
            voice_id: Optional voice ID
            
        Returns:
            Dict with success status, file path, and error if any
        """
        if not transcript or len(transcript) == 0:
            return {
                "success": False,
                "error": "Empty transcript",
                "file_path": None,
            }
        
        # Combine transcript segments into a single text
        transcript_text = ""
        for segment in transcript:
            text = segment.get("text", "").strip()
            if text:
                transcript_text += f"{text}. "
        
        return self.generate_audio(
            text=transcript_text,
            meeting_id=meeting_id,
            audio_type="transcript",
            voice_id=voice_id
        )
    
    def get_voices(self) -> Dict[str, Any]:
        """
        Get list of available voices from ElevenLabs
        
        Returns:
            Dict with success status and list of voices, or error
        """
        try:
            if not self.client:
                error_msg = "ElevenLabs API client not initialized (missing ELEVENLABS_API_KEY)"
                print(f"[TTS] ❌ {error_msg}", flush=True)
                return {
                    "success": False,
                    "error": error_msg,
                    "voices": [],
                }
            
            print("[TTS] 📋 Fetching available voices from ElevenLabs...", flush=True)
            
            # Fetch voices from ElevenLabs API
            voices_response = self.client.voices.get_all()
            
            # Extract voice information
            voices = []
            for voice in voices_response.voices:
                voice_id = voice.voice_id
                voice_data = {
                    "voice_id": voice_id,
                    "name": voice.name,
                    "description": getattr(voice, 'description', None) or "",
                    "category": getattr(voice, 'category', None) or "",
                    "labels": getattr(voice, 'labels', None) or {},
                    "preview_url": getattr(voice, 'preview_url', None) or "",
                    "bitmoji_url": self.get_voice_bitmoji(voice_id),
                    "emoji": self.get_voice_emoji(voice_id),  # Keep for backward compatibility
                }
                voices.append(voice_data)
            
            print(f"[TTS] ✅ Found {len(voices)} voices", flush=True)
            
            return {
                "success": True,
                "voices": voices,
                "error": None,
            }
            
        except Exception as e:
            error_msg = f"Error fetching voices: {str(e)}"
            print(f"[TTS] ❌ {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": error_msg,
                "voices": [],
            }

# Global instance
tts_service = TTSService()

