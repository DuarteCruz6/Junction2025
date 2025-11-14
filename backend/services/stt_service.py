"""
Speech-to-Text Service
Handles audio transcription and speaker diarization using ElevenLabs
"""

import os
from typing import List, Optional, Dict, Any
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import base64
import io
import wave
import asyncio
from collections import defaultdict

load_dotenv()

class STTService:
    """Service for speech-to-text transcription with speaker diarization"""
    
    def __init__(self):
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
        self.client = ElevenLabs(api_key=api_key)
        self.known_speakers: Dict[str, str] = {}  # speaker_name -> audio_file_path
        self.speaker_references: Dict[str, str] = {}  # speaker_name -> data_url
        
        # Streaming buffers: meeting_id -> list of audio chunks
        self.streaming_buffers: Dict[str, List[bytes]] = defaultdict(list)
        self.buffer_lock = asyncio.Lock()
        
        # Buffer configuration - optimized for lower latency
        self.MIN_BUFFER_DURATION = 0.3  # Minimum 0.3 seconds before processing (reduced for faster response)
        self.MAX_BUFFER_DURATION = 1.5   # Maximum 1.5 seconds (reduced from 3.0 for lower latency)
        self.SAMPLE_RATE = 16000         # 16kHz sample rate
        self.CHANNELS = 1                # Mono audio
        self.SAMPLE_WIDTH = 2            # 16-bit (2 bytes per sample)
        
    def register_speaker(self, name: str, audio_file_path: str):
        """Register a known speaker with their voice sample"""
        # Note: ElevenLabs may have different speaker registration - keeping for compatibility
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
                # Transcribe with ElevenLabs (supports diarization)
                # Run in executor since ElevenLabs API is synchronous
                loop = asyncio.get_event_loop()
                
                # Read file content first, then pass to executor
                with open(tmp_file_path, "rb") as audio_file:
                    audio_file_data = audio_file.read()
                
                # ElevenLabs speech_to_text.convert with diarization (run in executor)
                def transcribe():
                    # Create BytesIO inside executor to avoid file handle issues
                    audio_bytes = io.BytesIO(audio_file_data)
                    return self.client.speech_to_text.convert(
                        file=audio_bytes,
                        model_id="scribe_v1",  # ElevenLabs STT model
                        diarize=True,  # Enable speaker diarization
                    )
                
                transcription = await loop.run_in_executor(None, transcribe)
                
                # Convert to dict if it's an object
                if hasattr(transcription, 'dict'):
                    transcript_dict = transcription.dict()
                elif isinstance(transcription, dict):
                    transcript_dict = transcription
                else:
                    # Try to access as object
                    transcript_dict = {
                        'text': getattr(transcription, 'text', ''),
                        'segments': getattr(transcription, 'segments', [])
                    }
                
                # Format response from ElevenLabs
                segments = []
                
                # ElevenLabs returns segments with speaker info when diarize=True
                if 'segments' in transcript_dict and transcript_dict['segments']:
                    for segment in transcript_dict['segments']:
                        # Handle both dict and object formats
                        if isinstance(segment, dict):
                            segments.append({
                                "speaker": segment.get('speaker', segment.get('speaker_id', 'Unknown')),
                                "text": segment.get('text', ''),
                                "start": segment.get('start', segment.get('start_time', 0.0)),
                                "end": segment.get('end', segment.get('end_time', 0.0)),
                            })
                        else:
                            # Object format
                            segments.append({
                                "speaker": getattr(segment, 'speaker', getattr(segment, 'speaker_id', 'Unknown')),
                                "text": getattr(segment, 'text', ''),
                                "start": getattr(segment, 'start', getattr(segment, 'start_time', 0.0)),
                                "end": getattr(segment, 'end', getattr(segment, 'end_time', 0.0)),
                            })
                elif 'text' in transcript_dict:
                    # Single text response (no segments)
                    segments.append({
                        "speaker": "Unknown",
                        "text": transcript_dict['text'],
                        "start": 0.0,
                        "end": transcript_dict.get('duration', 0.0),
                    })
                elif hasattr(transcription, 'text'):
                    # Fallback: single segment with full text
                    segments.append({
                        "speaker": "Unknown",
                        "text": getattr(transcription, 'text', ''),
                        "start": 0.0,
                        "end": getattr(transcription, 'duration', 0.0),
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
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
        """Convert PCM audio data to WAV format"""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()
    
    def _calculate_audio_duration(self, pcm_data: bytes, sample_rate: int = 16000, sample_width: int = 2) -> float:
        """Calculate audio duration in seconds from PCM data"""
        num_samples = len(pcm_data) // sample_width
        return num_samples / sample_rate
    
    async def add_audio_chunk(
        self,
        audio_chunk: bytes,
        meeting_id: str,
        is_final: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Add audio chunk to buffer and process if buffer is ready
        
        Args:
            audio_chunk: PCM audio data (16-bit, 16kHz, mono)
            meeting_id: Meeting identifier
            is_final: Whether this is the final chunk
            
        Returns:
            Dict with transcription results if buffer was processed, None otherwise
        """
        async with self.buffer_lock:
            # Add chunk to buffer
            self.streaming_buffers[meeting_id].append(audio_chunk)
            
            # Calculate total buffer duration
            total_pcm = b''.join(self.streaming_buffers[meeting_id])
            buffer_duration = self._calculate_audio_duration(
                total_pcm, 
                self.SAMPLE_RATE, 
                self.SAMPLE_WIDTH
            )
            
            # Process if buffer is ready (min duration reached or max duration exceeded or final)
            should_process = (
                is_final or 
                buffer_duration >= self.MAX_BUFFER_DURATION or
                buffer_duration >= self.MIN_BUFFER_DURATION
            )
            
            if should_process and len(self.streaming_buffers[meeting_id]) > 0:
                # Process the buffer
                buffer_pcm = b''.join(self.streaming_buffers[meeting_id])
                self.streaming_buffers[meeting_id].clear()
                
                # Convert PCM to WAV
                wav_data = self._pcm_to_wav(
                    buffer_pcm,
                    self.SAMPLE_RATE,
                    self.CHANNELS,
                    self.SAMPLE_WIDTH
                )
                
                # Process asynchronously (don't block)
                # Note: callback will be set by the WebSocket handler
                asyncio.create_task(self._process_buffer(wav_data, meeting_id, is_final, None))
                
                # Return immediately (processing happens in background)
                return {
                    "success": True,
                    "status": "processing",
                    "buffer_duration": buffer_duration,
                    "is_final": is_final
                }
        
        return None
    
    async def _process_buffer(
        self,
        wav_data: bytes,
        meeting_id: str,
        is_final: bool,
        callback=None
    ):
        """Process audio buffer with ElevenLabs transcription"""
        try:
            # print(f"[STT] Processing audio buffer for meeting {meeting_id} ({len(wav_data)} bytes)")  # DEBUG
            
            # Use the existing transcription method
            result = await self.transcribe_with_diarization(
                audio_data=wav_data,
                audio_format="wav",
                language=None  # Auto-detect
            )
            
            # print(f"[STT] Transcription result: success={result.get('success')}, segments={len(result.get('segments', []))}")  # DEBUG
            
            if not result.get("success"):
                print(f"[STT] Transcription failed: {result.get('error', 'Unknown error')}")  # Keep error messages
            
            # Call callback if provided (for WebSocket updates)
            if callback:
                # print(f"[STT] Calling callback with {len(result.get('segments', []))} segments")  # DEBUG
                await callback(result, meeting_id)
            # else:
            #     print(f"[STT] No callback provided, skipping WebSocket update")  # DEBUG
            
            return result
            
        except Exception as e:
            print(f"[STT] Error processing audio buffer for meeting {meeting_id}: {e}")  # Keep error messages
            import traceback
            traceback.print_exc()
            error_result = {
                "success": False,
                "error": str(e),
                "segments": [],
                "full_text": ""
            }
            if callback:
                await callback(error_result, meeting_id)
            return error_result
    
    async def transcribe_streaming(
        self,
        audio_chunk: bytes,
        meeting_id: str,
        is_final: bool = False
    ) -> Dict[str, Any]:
        """
        Process streaming audio chunk (for real-time transcription)
        
        This method buffers chunks and processes them when ready.
        Returns immediately, processing happens asynchronously.
        """
        return await self.add_audio_chunk(audio_chunk, meeting_id, is_final)
    
    def clear_buffer(self, meeting_id: str):
        """Clear the audio buffer for a meeting"""
        if meeting_id in self.streaming_buffers:
            del self.streaming_buffers[meeting_id]


# Singleton instance
stt_service = STTService()

