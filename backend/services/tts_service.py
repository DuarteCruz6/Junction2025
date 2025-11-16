"""
TTS Service
Handles text-to-speech conversion using ElevenLabs API
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

class TTSService:
    """Service for Text-to-Speech conversion using ElevenLabs"""
    
    # Emoji mapping for voices
    VOICE_EMOJI_MAP = {
        "2EiwWnXFnvU5JabPnv8n": "🎭",  # Clyde
        "CwhRBWXzGAHq8TQ4Fs17": "😊",  # Roger
        "EXAVITQu4vr4xnSDxMaL": "👩‍💼",  # Sarah
        "FGY2WhTYpPnrIDTdsKH5": "☀️",  # Laura
        "IKne3meq5aSn9XLyUdCD": "⚡",  # Charlie
        "JBFqnCBsd6RMkjVDRZzb": "🎤",  # George
        "N2lVS1w4EtoT3dr4eOWO": "🎪",  # Callum
        "SAz9YHcvj6GT2YYXdXww": "🌊",  # River
        "SOYHLrjzK2X1ezoPC6cr": "⚔️",  # Harry
        "TX3LPaxmHKxFdv7VOQHJ": "🔥",  # Liam
        "Xb7hH8MSUJpSbSDYk0k2": "📚",  # Alice
        "XrExE9yKIg1WjnnlVkGX": "💼",  # Matilda
        "bIHbv24MWmeRgasZH58o": "🏖️",  # Will
        "cgSgspJ2msm6clMCkdW9": "✨",  # Jessica
        "cjVigY5qzO86Huf0OWal": "🎩",  # Eric
        "iP95p4xoKVk53GoZ742B": "🌿",  # Chris
        "nPczCjzI2devNBz1zQrb": "🎙️",  # Brian
        "onwK4e9ZLuTAKqWW03F9": "📺",  # Daniel
        "pFZP5JQG7iQjIQuC4Bku": "🎀",  # Lily
        "pqHfZKP75CvOlQylNhV4": "👴",  # Bill
    }
    
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
    
    def get_voice_emoji(self, voice_id: str) -> str:
        """Get emoji for a voice ID"""
        return self.VOICE_EMOJI_MAP.get(voice_id, "🎙️")  # Default emoji
    
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
        # Format: "Speaker: text. Speaker: text."
        transcript_text = ""
        for segment in transcript:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "").strip()
            if text:
                transcript_text += f"{speaker}: {text}. "
        
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
                    "emoji": self.get_voice_emoji(voice_id),
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

