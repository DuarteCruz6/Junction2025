"""
Speech-to-Text Service
Handles audio transcription and speaker diarization using ElevenLabs
Supports both batch API (scribe_v1) and realtime streaming API (scribe_v2_realtime)
"""

import os
from typing import List, Optional, Dict, Any, Callable
from elevenlabs.client import ElevenLabs
from elevenlabs import RealtimeEvents
from elevenlabs.realtime import AudioFormat, RealtimeAudioOptions
from dotenv import load_dotenv
import base64
import io
import wave
import asyncio
import json
from collections import defaultdict

load_dotenv()

class STTService:
    """Service for speech-to-text transcription with speaker diarization"""
    
    def __init__(self):
        print("[STT] 🔧 Initializing STT Service...")
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
        print("[STT] ✅ ElevenLabs API key found")
        self.client = ElevenLabs(api_key=api_key)
        print("[STT] ✅ ElevenLabs client initialized")
        self.known_speakers: Dict[str, str] = {}  # speaker_name -> audio_file_path
        self.speaker_references: Dict[str, str] = {}  # speaker_name -> data_url
        
        # Streaming buffers: meeting_id -> list of audio chunks (for batch API fallback)
        self.streaming_buffers: Dict[str, List[bytes]] = defaultdict(list)
        self.buffer_lock = asyncio.Lock()
        
        # Batch processing buffers: meeting_id -> list of audio chunks (for periodic diarization)
        self.batch_processing_buffers: Dict[str, List[bytes]] = defaultdict(list)
        self.batch_buffer_lock = asyncio.Lock()
        
        # Track last processing time for each meeting (to avoid cutting mid-phrase)
        self.last_batch_process_time: Dict[str, float] = {}
        self.last_committed_time: Dict[str, float] = {}  # Track when last committed transcript was received
        
        # Buffer configuration - optimized for better accuracy
        # Longer buffers provide more context for better transcription quality
        self.MIN_BUFFER_DURATION = 1.5  # Minimum 1.5 seconds for better context
        self.MAX_BUFFER_DURATION = 4.0   # Maximum 4.0 seconds (balance between latency and quality)
        self.SAMPLE_RATE = 16000         # 16kHz sample rate
        self.CHANNELS = 1                # Mono audio
        self.SAMPLE_WIDTH = 2            # 16-bit (2 bytes per sample)
        
        # Batch processing configuration
        self.BATCH_PROCESS_INTERVAL = 60.0  # Process every 60 seconds (not used anymore, kept for compatibility)
        self.MIN_SILENCE_FOR_CUT = 1.0  # Wait for 1 second of silence before cutting (avoid mid-phrase)
        self.MIN_AUDIO_FOR_DIARIZATION = 1.0  # Minimum 1 second of audio to process (allows processing after each phrase, even short ones)
        self.MAX_AUDIO_BEFORE_FORCE = 30.0  # Force process if we have 30 seconds of audio (prevents buffer overflow)
        
        # Language configuration (can be set per meeting)
        self.default_language = os.getenv("STT_LANGUAGE", None)  # e.g., "en", "pt", "es"
        
        # Text post-processing settings
        self.min_text_length = 2  # Minimum characters to consider valid transcription
        self.enable_text_cleaning = True
        
        # Realtime API connections: meeting_id -> connection
        self.realtime_connections: Dict[str, Any] = {}
        self.realtime_lock = asyncio.Lock()
        
        # Use realtime API by default (can be disabled via env var)
        self.use_realtime = os.getenv("STT_USE_REALTIME", "true").lower() == "true"
        
        print(f"[STT] ✅ STT Service initialized (Sample Rate: {self.SAMPLE_RATE}Hz, Channels: {self.CHANNELS})")
        print(f"[STT] 📡 Realtime API: {'Enabled' if self.use_realtime else 'Disabled (using batch API)'}")
        
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
                
                audio_size_mb = len(audio_file_data) / (1024 * 1024)
                audio_duration = len(audio_file_data) / (self.SAMPLE_RATE * self.SAMPLE_WIDTH * self.CHANNELS)
                # ElevenLabs speech_to_text.convert with diarization (run in executor)
                def transcribe():
                    # Create BytesIO inside executor to avoid file handle issues
                    audio_bytes = io.BytesIO(audio_file_data)
                    
                    # Build transcription parameters
                    transcribe_params = {
                        "file": audio_bytes,
                        "model_id": "scribe_v1",  # ElevenLabs STT model
                        "diarize": True,  # Enable speaker diarization
                    }
                    
                    # Add language if specified (ElevenLabs supports language hints)
                    if language:
                        transcribe_params["language"] = language
                    elif self.default_language:
                        transcribe_params["language"] = self.default_language
                    
                    result = self.client.speech_to_text.convert(**transcribe_params)
                    return result
                
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
                    # Debug: log first segment structure to understand API response
                    first_seg = transcript_dict['segments'][0]
                    if isinstance(first_seg, dict):
                        print(f"[STT] [Diarization] 🔍 First segment keys: {list(first_seg.keys())}", flush=True)
                        print(f"[STT] [Diarization] 🔍 First segment sample: {str(first_seg)[:200]}", flush=True)
                    
                    for idx, segment in enumerate(transcript_dict['segments']):
                        # Handle both dict and object formats
                        if isinstance(segment, dict):
                            # Try multiple possible keys for speaker
                            speaker = (
                                segment.get('speaker') or 
                                segment.get('speaker_id') or 
                                segment.get('speaker_label') or
                                segment.get('speaker_tag') or
                                'Unknown'
                            )
                            raw_text = segment.get('text', '')
                            start = segment.get('start', segment.get('start_time', 0.0))
                            end = segment.get('end', segment.get('end_time', 0.0))
                        else:
                            # Object format - try multiple attributes
                            speaker = (
                                getattr(segment, 'speaker', None) or
                                getattr(segment, 'speaker_id', None) or
                                getattr(segment, 'speaker_label', None) or
                                getattr(segment, 'speaker_tag', None) or
                                'Unknown'
                            )
                            raw_text = getattr(segment, 'text', '')
                            start = getattr(segment, 'start', getattr(segment, 'start_time', 0.0))
                            end = getattr(segment, 'end', getattr(segment, 'end_time', 0.0))
                        
                        # Clean and validate text
                        if self.enable_text_cleaning:
                            text = self._clean_text(raw_text)
                        else:
                            text = raw_text.strip()
                        
                        # Only add segment if text is valid
                        if self._is_valid_transcription(text):
                            segments.append({
                                "speaker": speaker,
                                "text": text,
                                "start": start,
                                "end": end,
                            })
                elif 'text' in transcript_dict:
                    # Single text response (no segments)
                    raw_text = transcript_dict['text']
                    if self.enable_text_cleaning:
                        text = self._clean_text(raw_text)
                    else:
                        text = raw_text.strip()
                    
                    if self._is_valid_transcription(text):
                        segments.append({
                            "speaker": "Unknown",
                            "text": text,
                            "start": 0.0,
                            "end": transcript_dict.get('duration', 0.0),
                        })
                elif hasattr(transcription, 'text'):
                    # Fallback: single segment with full text
                    raw_text = getattr(transcription, 'text', '')
                    if self.enable_text_cleaning:
                        text = self._clean_text(raw_text)
                    else:
                        text = raw_text.strip()
                    
                    if self._is_valid_transcription(text):
                        segments.append({
                            "speaker": "Unknown",
                            "text": text,
                            "start": 0.0,
                            "end": getattr(transcription, 'duration', 0.0),
                        })
                
                full_text = " ".join([s["text"] for s in segments])
                
                return {
                    "success": True,
                    "segments": segments,
                    "full_text": full_text,
                }
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            print(f"[STT] ❌ Transcription error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "full_text": "",
            }
    
    def _normalize_audio_gain(self, pcm_data: bytes, sample_width: int = 2) -> bytes:
        """
        Normalize audio gain to improve transcription quality
        Prevents audio that's too quiet or too loud
        Uses numpy if available, otherwise uses basic Python implementation
        """
        try:
            import numpy as np
            use_numpy = True
        except ImportError:
            use_numpy = False
        
        try:
            if sample_width == 2:
                # 16-bit signed integers
                if use_numpy:
                    # Use numpy for efficient processing
                    samples = np.frombuffer(pcm_data, dtype=np.int16)
                    
                    # Skip normalization if audio is too short or silent
                    if len(samples) < 100 or np.max(np.abs(samples)) == 0:
                        return pcm_data
                    
                    # Calculate current peak level
                    peak = np.max(np.abs(samples))
                    max_peak = 32767  # Maximum for 16-bit signed
                    
                    # Only normalize if audio is too quiet (below 30% of max)
                    if peak < max_peak * 0.3:
                        # Normalize to 70% of max to leave headroom
                        target_peak = int(max_peak * 0.7)
                        if peak > 0:
                            gain_factor = target_peak / peak
                            samples = (samples * gain_factor).astype(np.int16)
                            # Clip to prevent overflow
                            samples = np.clip(samples, -max_peak, max_peak - 1)
                    
                    return samples.tobytes()
                else:
                    # Fallback: basic Python implementation
                    import struct
                    samples = list(struct.unpack(f'<{len(pcm_data)//2}h', pcm_data))
                    
                    if len(samples) < 100:
                        return pcm_data
                    
                    # Find peak
                    peak = max(abs(s) for s in samples)
                    max_peak = 32767
                    
                    # Only normalize if too quiet
                    if peak < max_peak * 0.3 and peak > 0:
                        target_peak = int(max_peak * 0.7)
                        gain_factor = target_peak / peak
                        samples = [int(min(max(s * gain_factor, -max_peak), max_peak - 1)) for s in samples]
                        return struct.pack(f'<{len(samples)}h', *samples)
                    
                    return pcm_data
            else:
                # For other bit depths, return as-is
                return pcm_data
        except Exception as e:
            # If normalization fails, return original audio
            print(f"[STT] ⚠️  Audio normalization failed: {e}, using original audio")
            return pcm_data
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
        """Convert PCM audio data to WAV format with optional normalization"""
        # Normalize audio gain for better transcription quality
        normalized_pcm = self._normalize_audio_gain(pcm_data, sample_width)
        
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(normalized_pcm)
        return wav_buffer.getvalue()
    
    def _calculate_audio_duration(self, pcm_data: bytes, sample_rate: int = 16000, sample_width: int = 2) -> float:
        """Calculate audio duration in seconds from PCM data"""
        num_samples = len(pcm_data) // sample_width
        return num_samples / sample_rate
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize transcribed text for better display quality
        
        - Removes excessive whitespace
        - Fixes common transcription errors
        - Normalizes punctuation
        - Capitalizes sentences
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove excessive whitespace (multiple spaces/tabs)
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common transcription issues
        # Remove filler words that are often mis-transcribed
        filler_words = ['um', 'uh', 'er', 'ah', 'eh']
        words = text.split()
        cleaned_words = []
        for word in words:
            # Remove standalone filler words (case-insensitive)
            if word.lower().rstrip('.,!?;:') not in filler_words:
                cleaned_words.append(word)
        
        text = ' '.join(cleaned_words)
        
        # Capitalize first letter of sentence
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        # Ensure sentence ends with punctuation if it looks complete
        if text and not text[-1] in '.!?':
            # Add period if sentence seems complete (has multiple words)
            if len(text.split()) > 3:
                text += '.'
        
        return text.strip()
    
    def _is_valid_transcription(self, text: str) -> bool:
        """Check if transcription is valid and should be displayed"""
        if not text:
            return False
        
        # Check minimum length (reduced threshold for realtime API)
        text_stripped = text.strip()
        if len(text_stripped) < 1:  # Allow single characters for partial transcripts
            return False
        
        # For partial transcripts, be more lenient
        # Only filter out obvious noise (all punctuation, all numbers, etc.)
        import re
        
        # Filter out transcriptions that are ONLY punctuation or special chars
        alphanumeric_chars = len(re.sub(r'[^a-zA-Z0-9]', '', text_stripped))
        if alphanumeric_chars == 0 and len(text_stripped) > 0:
            # All punctuation/special chars - likely noise
            return False
        
        # Filter out transcriptions that are mostly non-alphanumeric (but allow some)
        if len(text_stripped) > 5 and alphanumeric_chars < len(text_stripped) * 0.2:
            # Less than 20% alphanumeric for longer text - likely noise
            return False
        
        # Allow short transcriptions (they might be valid words or partial words)
        # Don't filter based on word count for realtime API
        
        return True
    
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
            # Use the existing transcription method
            result = await self.transcribe_with_diarization(
                audio_data=wav_data,
                audio_format="wav",
                language=None  # Auto-detect
            )
            
            # Call callback if provided (for WebSocket updates)
            if callback:
                await callback(result, meeting_id)
            
            return result
            
        except Exception as e:
            print(f"[STT] ❌ Error processing audio buffer for meeting {meeting_id}: {e}")
            import traceback
            traceback.print_exc()
            error_result = {
                "success": False,
                "error": str(e),
                "segments": [],
                "full_text": ""
            }
            if callback:
                print(f"[STT] 📤 Calling callback with error result")
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
    
    async def connect_realtime(
        self,
        meeting_id: str,
        on_partial_transcript: Optional[Callable] = None,
        on_committed_transcript: Optional[Callable] = None,
        language: Optional[str] = None
    ) -> bool:
        """
        Connect to ElevenLabs realtime API for a meeting
        
        Args:
            meeting_id: Meeting identifier
            on_partial_transcript: Callback for partial transcripts (interim results)
            on_committed_transcript: Callback for committed transcripts (final results)
            language: Optional language code (e.g., 'en', 'pt')
            
        Returns:
            True if connection successful, False otherwise
        """
        async with self.realtime_lock:
            if meeting_id in self.realtime_connections:
                print(f"[STT] ⚠️  Realtime connection already exists for meeting {meeting_id}")
                return True
            
            try:
                print(f"[STT] 🔌 Connecting to ElevenLabs realtime API for meeting {meeting_id}...")
                
                # Build connection config
                # For manual audio mode, use RealtimeAudioOptions as per documentation
                # https://elevenlabs.io/docs/cookbooks/speech-to-text/streaming
                
                # Create RealtimeAudioOptions for manual audio chunking
                # This matches the documentation pattern (similar to RealtimeUrlOptions for URL streaming)
                audio_options = RealtimeAudioOptions(
                    model_id="scribe_v2_realtime",
                    audio_format=AudioFormat.PCM_16000,  # 16-bit PCM, little-endian, 16kHz
                    sample_rate=self.SAMPLE_RATE,
                    include_timestamps=True,
                )
                
                # Only set language if explicitly provided (for auto-detection, leave it unset)
                # For live translation, we want the API to auto-detect the language
                if language:
                    audio_options.language = language
                    print(f"[STT] 🌐 Using explicit language: {language}")
                else:
                    print(f"[STT] 🌐 Auto-detecting language (no language specified)")
                
                # Connect to realtime API using RealtimeAudioOptions
                # This matches the documentation: await elevenlabs.speech_to_text.realtime.connect(RealtimeAudioOptions(...))
                connection = await self.client.speech_to_text.realtime.connect(audio_options)
                
                # Set up event handlers
                # Note: connection.on() takes (event, callback) - not a decorator
                # The library expects synchronous callbacks, so we wrap async handlers
                def on_session_started(data):
                    print(f"[STT] ✅ Realtime session started for meeting {meeting_id}")
                
                async def _on_partial_async(data):
                    try:
                        # Debug: log data structure to check for speaker info
                        if isinstance(data, dict):
                            # Check if speaker information is available (even if not officially supported)
                            speaker = data.get("speaker", data.get("speaker_id", None))
                            text = data.get("text", "")
                            if speaker:
                                print(f"[STT] [Diarization] 🎤 Partial transcript with speaker: {speaker}")
                        else:
                            text = str(data)
                            speaker = None
                        
                        if text and on_partial_transcript:
                            # Clean text before sending
                            if self.enable_text_cleaning:
                                text = self._clean_text(text)
                            # Be more lenient with partial transcripts - show them even if short
                            if text and len(text.strip()) > 0:
                                transcript_data = {
                                    "type": "partial",
                                    "text": text,
                                    "meeting_id": meeting_id
                                }
                                # Include speaker if available
                                if speaker is not None:
                                    transcript_data["speaker"] = speaker
                                await on_partial_transcript(transcript_data)
                    except Exception as e:
                        print(f"[STT] ⚠️  Error handling partial transcript: {e}")
                
                def on_partial(data):
                    # Wrap async handler in a task to avoid RuntimeWarning
                    asyncio.create_task(_on_partial_async(data))
                
                async def _on_committed_async(data):
                    # Check for speaker information in committed transcript
                    if isinstance(data, dict):
                        speaker = data.get("speaker", data.get("speaker_id", None))
                        text = data.get("text", "")
                        if speaker:
                            print(f"[STT] [Diarization] 🎤 Committed transcript with speaker: {speaker}")
                    else:
                        text = str(data)
                        speaker = None
                    
                    if text and on_committed_transcript:
                        # Clean text before sending
                        if self.enable_text_cleaning:
                            text = self._clean_text(text)
                        if self._is_valid_transcription(text):
                            transcript_data = {
                                "type": "committed",
                                "text": text,
                                "meeting_id": meeting_id
                            }
                            # Include speaker if available
                            if speaker is not None:
                                transcript_data["speaker"] = speaker
                            await on_committed_transcript(transcript_data)
                
                def on_committed(data):
                    # Wrap async handler in a task to avoid RuntimeWarning
                    asyncio.create_task(_on_committed_async(data))
                
                async def _on_committed_with_timestamps_async(data):
                    # Check for speaker information in committed transcript with timestamps
                    if isinstance(data, dict):
                        speaker = data.get("speaker", data.get("speaker_id", None))
                        text = data.get("text", "")
                        words = data.get("words", [])
                        if speaker:
                            print(f"[STT] [Diarization] 🎤 Committed transcript with timestamps and speaker: {speaker}")
                    else:
                        text = str(data)
                        words = []
                        speaker = None
                    
                    if text and on_committed_transcript:
                        # Clean text before sending
                        if self.enable_text_cleaning:
                            text = self._clean_text(text)
                        if self._is_valid_transcription(text):
                            transcript_data = {
                                "type": "committed",
                                "text": text,
                                "words": words,
                                "meeting_id": meeting_id
                            }
                            # Include speaker if available
                            if speaker is not None:
                                transcript_data["speaker"] = speaker
                            await on_committed_transcript(transcript_data)
                
                def on_committed_with_timestamps(data):
                    # Wrap async handler in a task to avoid RuntimeWarning
                    asyncio.create_task(_on_committed_with_timestamps_async(data))
                
                async def _on_error_async(error):
                    error_msg = str(error) if error else "Unknown error"
                    print(f"[STT] ❌ Realtime API error for meeting {meeting_id}: {error_msg}")
                    
                    # Try to notify callbacks about the error
                    if on_committed_transcript:
                        try:
                            await on_committed_transcript({
                                "type": "error",
                                "error": error_msg,
                                "meeting_id": meeting_id
                            })
                        except Exception as e:
                            print(f"[STT] ⚠️  Error notifying callback: {e}")
                    
                    # Clean up connection on error
                    async with self.realtime_lock:
                        if meeting_id in self.realtime_connections:
                            del self.realtime_connections[meeting_id]
                
                def on_error(error):
                    # Wrap async handler in a task to avoid RuntimeWarning
                    asyncio.create_task(_on_error_async(error))
                
                async def _on_auth_error_async(data):
                    error_msg = data.get("error", "Authentication error") if isinstance(data, dict) else str(data)
                    print(f"[STT] ❌ Realtime API auth error for meeting {meeting_id}: {error_msg}")
                    
                    # Try to notify callbacks about the error
                    if on_committed_transcript:
                        try:
                            await on_committed_transcript({
                                "type": "error",
                                "error": f"Authentication error: {error_msg}",
                                "meeting_id": meeting_id
                            })
                        except Exception as e:
                            print(f"[STT] ⚠️  Error notifying callback: {e}")
                    
                    # Clean up connection on error
                    async with self.realtime_lock:
                        if meeting_id in self.realtime_connections:
                            del self.realtime_connections[meeting_id]
                
                def on_auth_error(data):
                    # Wrap async handler in a task to avoid RuntimeWarning
                    asyncio.create_task(_on_auth_error_async(data))
                
                def on_close():
                    print(f"[STT] 🔌 Realtime connection closed for meeting {meeting_id}")
                    # Note: on_close might not be async, handle cleanup in a task if needed
                    async def cleanup():
                        async with self.realtime_lock:
                            if meeting_id in self.realtime_connections:
                                del self.realtime_connections[meeting_id]
                    asyncio.create_task(cleanup())
                
                # Register event handlers (connection.on() takes event and callback)
                connection.on(RealtimeEvents.SESSION_STARTED, on_session_started)
                connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, on_partial)
                connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, on_committed)
                connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT_WITH_TIMESTAMPS, on_committed_with_timestamps)
                connection.on(RealtimeEvents.ERROR, on_error)
                connection.on(RealtimeEvents.AUTH_ERROR, on_auth_error)
                connection.on(RealtimeEvents.CLOSE, on_close)
                
                # Store connection
                self.realtime_connections[meeting_id] = {
                    "connection": connection,
                    "on_partial": on_partial_transcript,
                    "on_committed": on_committed_transcript
                }
                
                print(f"[STT] ✅ Realtime API connected for meeting {meeting_id}")
                return True
                
            except Exception as e:
                print(f"[STT] ❌ Failed to connect to realtime API for meeting {meeting_id}: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    async def send_audio_to_realtime(
        self,
        meeting_id: str,
        audio_chunk: bytes
    ) -> bool:
        """
        Send audio chunk to ElevenLabs realtime API
        
        Args:
            meeting_id: Meeting identifier
            audio_chunk: PCM audio data (16-bit, 16kHz, mono)
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Skip empty chunks
        if not audio_chunk or len(audio_chunk) == 0:
            return True  # Not an error, just nothing to send
        
        async with self.realtime_lock:
            if meeting_id not in self.realtime_connections:
                print(f"[STT] ⚠️  No realtime connection for meeting {meeting_id}")
                return False
            
            try:
                connection = self.realtime_connections[meeting_id]["connection"]
                
                # Validate connection is still active
                if not connection:
                    print(f"[STT] ⚠️  Realtime connection is None for meeting {meeting_id}")
                    del self.realtime_connections[meeting_id]
                    return False
                
                # Convert PCM to base64
                audio_base64 = base64.b64encode(audio_chunk).decode("utf-8")
                
                # Send audio chunk with error handling
                try:
                    await connection.send({
                        "audio_base_64": audio_base64,
                        "sample_rate": self.SAMPLE_RATE,
                    })
                    return True
                except AttributeError as e:
                    # Connection object doesn't have send method or is closed
                    print(f"[STT] ⚠️  Connection object invalid: {e}")
                    if meeting_id in self.realtime_connections:
                        del self.realtime_connections[meeting_id]
                    return False
                except Exception as send_error:
                    # Other send errors
                    print(f"[STT] ⚠️  Error sending audio chunk: {send_error}")
                    # Don't delete connection on send error - might be temporary
                    return False
                
            except KeyError:
                # Connection was removed by another thread
                print(f"[STT] ⚠️  Connection removed for meeting {meeting_id}")
                return False
            except Exception as e:
                print(f"[STT] ❌ Unexpected error sending audio to realtime API for meeting {meeting_id}: {e}")
                import traceback
                traceback.print_exc()
                # Clean up connection on unexpected error
                if meeting_id in self.realtime_connections:
                    del self.realtime_connections[meeting_id]
                return False
    
    async def commit_realtime_transcript(self, meeting_id: str) -> bool:
        """
        Commit current transcript segment in realtime API
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            True if committed successfully, False otherwise
        """
        async with self.realtime_lock:
            if meeting_id not in self.realtime_connections:
                return False
            
            try:
                connection = self.realtime_connections[meeting_id]["connection"]
                await connection.commit()
                return True
            except Exception as e:
                print(f"[STT] ❌ Error committing transcript for meeting {meeting_id}: {e}")
                return False
    
    async def disconnect_realtime(self, meeting_id: str):
        """Disconnect from ElevenLabs realtime API for a meeting"""
        async with self.realtime_lock:
            if meeting_id in self.realtime_connections:
                try:
                    connection = self.realtime_connections[meeting_id]["connection"]
                    await connection.close()
                except Exception as e:
                    print(f"[STT] ⚠️  Error closing realtime connection for meeting {meeting_id}: {e}")
                finally:
                    del self.realtime_connections[meeting_id]
                    print(f"[STT] 🔌 Disconnected realtime API for meeting {meeting_id}")
    
    def clear_buffer(self, meeting_id: str):
        """Clear the audio buffer for a meeting"""
        if meeting_id in self.streaming_buffers:
            del self.streaming_buffers[meeting_id]
    
    async def add_audio_to_batch_buffer(
        self,
        audio_chunk: bytes,
        meeting_id: str
    ):
        """
        Add audio chunk to batch processing buffer (for periodic diarization)
        This runs in parallel with realtime transcription
        """
        async with self.batch_buffer_lock:
            self.batch_processing_buffers[meeting_id].append(audio_chunk)
            # Calculate current buffer size for debugging
            total_pcm = b''.join(self.batch_processing_buffers[meeting_id])
            buffer_duration = self._calculate_audio_duration(
                total_pcm,
                self.SAMPLE_RATE,
                self.SAMPLE_WIDTH
            )
            if len(self.batch_processing_buffers[meeting_id]) % 10 == 0:  # Log every 10 chunks
                print(f"[STT] [Diarization] 📦 Batch buffer: {len(self.batch_processing_buffers[meeting_id])} chunks, {buffer_duration:.1f}s audio", flush=True)
    
    async def process_batch_buffer_with_diarization(
        self,
        meeting_id: str,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Process accumulated audio buffer with diarization (batch API)
        
        Args:
            meeting_id: Meeting identifier
            force: If True, process immediately even if conditions aren't met
            
        Returns:
            Dict with transcription results if processed, None otherwise
        """
        import time
        current_time = time.time()
        
        async with self.batch_buffer_lock:
            if meeting_id not in self.batch_processing_buffers:
                return None
            
            buffer_chunks = self.batch_processing_buffers[meeting_id]
            if not buffer_chunks:
                return None
            
            # Calculate buffer duration
            total_pcm = b''.join(buffer_chunks)
            buffer_duration = self._calculate_audio_duration(
                total_pcm,
                self.SAMPLE_RATE,
                self.SAMPLE_WIDTH
            )
            
            # Check if we should process
            last_process_time = self.last_batch_process_time.get(meeting_id, 0)
            time_since_last_process = current_time - last_process_time
            last_committed = self.last_committed_time.get(meeting_id, 0)
            time_since_last_committed = current_time - last_committed
            
            # Process if:
            # 1. Forced (e.g., meeting ended)
            # 2. We have enough audio (at least MIN_AUDIO_FOR_DIARIZATION seconds) AND we've had silence (no new commits) for MIN_SILENCE_FOR_CUT seconds
            # 3. OR we have MAX_AUDIO_BEFORE_FORCE seconds of audio (process anyway to avoid buffer overflow)
            # Note: Processes on silence detection after each phrase/sentence
            should_process = force or (
                buffer_duration >= self.MIN_AUDIO_FOR_DIARIZATION and  # At least 2 seconds of audio (one phrase)
                (
                    time_since_last_committed >= self.MIN_SILENCE_FOR_CUT or  # Natural pause detected (1 second silence)
                    buffer_duration >= self.MAX_AUDIO_BEFORE_FORCE  # Or we have 30 seconds of audio (process anyway)
                )
            )
            
            if not should_process:
                # Debug: log why we're not processing (but only occasionally to avoid spam)
                import time as time_module
                last_log_time = getattr(self, '_last_wait_log_time', {}).get(meeting_id, 0)
                current_time_check = time_module.time()
                
                # Only log every 30 seconds to avoid spam
                if current_time_check - last_log_time > 30:
                    if buffer_duration < self.MIN_AUDIO_FOR_DIARIZATION:
                        print(f"[STT] [Diarization] ⏸️  Waiting: {buffer_duration:.1f}s audio (need {self.MIN_AUDIO_FOR_DIARIZATION}s minimum), {time_since_last_committed:.1f}s since last commit", flush=True)
                    elif time_since_last_committed < self.MIN_SILENCE_FOR_CUT and buffer_duration < self.MAX_AUDIO_BEFORE_FORCE:
                        print(f"[STT] [Diarization] ⏸️  Waiting: {time_since_last_committed:.1f}s since commit (need {self.MIN_SILENCE_FOR_CUT}s silence), {buffer_duration:.1f}s audio ready", flush=True)
                    
                    if not hasattr(self, '_last_wait_log_time'):
                        self._last_wait_log_time = {}
                    self._last_wait_log_time[meeting_id] = current_time_check
                return None
            
            # Get buffer and clear it
            buffer_pcm = b''.join(buffer_chunks)
            self.batch_processing_buffers[meeting_id].clear()
            self.last_batch_process_time[meeting_id] = current_time
            
            print(f"[STT] [Diarization] 🔄 Processing batch buffer: {buffer_duration:.2f}s of audio, {len(buffer_chunks)} chunks", flush=True)
        
        # Convert PCM to WAV
        wav_data = self._pcm_to_wav(
            buffer_pcm,
            self.SAMPLE_RATE,
            self.CHANNELS,
            self.SAMPLE_WIDTH
        )
        
        # Process with batch API (with diarization)
        try:
            result = await self.transcribe_with_diarization(
                audio_data=wav_data,
                audio_format="wav",
                language=None  # Auto-detect
            )
            
            if result.get("success"):
                segments = result.get('segments', [])
                speakers = set(seg.get('speaker', 'Unknown') for seg in segments)
                print(f"[STT] [Diarization] ✅ Batch diarization complete: {len(segments)} segments, {len(speakers)} speakers: {speakers}", flush=True)
            else:
                print(f"[STT] [Diarization] ❌ Batch diarization failed: {result.get('error', 'Unknown error')}", flush=True)
            
            return result
        except Exception as e:
            print(f"[STT] ❌ Error processing batch buffer: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "full_text": ""
            }
    
    def mark_committed_transcript(self, meeting_id: str):
        """Mark that a committed transcript was received (for detecting natural pauses)"""
        import time
        self.last_committed_time[meeting_id] = time.time()
        # Background task will check for silence and process (checks every 5 seconds)
    
    def clear_batch_buffer(self, meeting_id: str):
        """Clear the batch processing buffer for a meeting (synchronous)"""
        # Note: This is called from both sync and async contexts
        # We'll use a simple synchronous approach since we're just deleting dict entries
        # The lock is async, but dict deletion is thread-safe in Python
        if meeting_id in self.batch_processing_buffers:
            del self.batch_processing_buffers[meeting_id]
        if meeting_id in self.last_batch_process_time:
            del self.last_batch_process_time[meeting_id]
        if meeting_id in self.last_committed_time:
            del self.last_committed_time[meeting_id]


# Singleton instance
print("[STT] 🚀 Creating STT Service singleton instance...")
stt_service = STTService()
print("[STT] ✅ STT Service singleton ready")

