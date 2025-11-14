"""
Speech-to-Text Service using Google Cloud Speech-to-Text V2
Supports real-time streaming with speaker diarization
"""

import os
from typing import Optional, Dict, List, AsyncGenerator
from google.api_core.client_options import ClientOptions
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech as cloud_speech_types
from dotenv import load_dotenv

load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
LANGUAGE_CODE = "en-US"  # Can be made configurable


class STTService:
    """Service for handling Speech-to-Text with speaker diarization"""
    
    def __init__(self):
        """Initialize the STT service with Google Cloud client"""
        if not PROJECT_ID:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        client_options = ClientOptions(api_endpoint=API_ENDPOINT)
        self.client = SpeechClient(client_options=client_options)
        self.project_id = PROJECT_ID
        self.location = LOCATION
        self.recognizer = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"
        
        # Active streaming sessions
        self.active_sessions: Dict[str, any] = {}
    
    def create_recognition_config(
        self,
        enable_diarization: bool = True,
        min_speakers: int = 1,
        max_speakers: int = 10,
        language_code: str = LANGUAGE_CODE,
    ) -> cloud_speech_types.RecognitionConfig:
        """Create recognition configuration with diarization"""
        config = cloud_speech_types.RecognitionConfig(
            auto_decoding_config=cloud_speech_types.AutoDetectDecodingConfig(),
            language_codes=[language_code],
            model="chirp",  # Use the "chirp" model for better accuracy
            features=cloud_speech_types.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
        )
        
        # Add speaker diarization if enabled
        if enable_diarization:
            config.features.diarization_config = cloud_speech_types.SpeakerDiarizationConfig(
                min_speaker_count=min_speakers,
                max_speaker_count=max_speakers,
            )
        
        return config
    
    def create_streaming_config(
        self,
        enable_diarization: bool = True,
        min_speakers: int = 1,
        max_speakers: int = 10,
    ) -> cloud_speech_types.StreamingRecognitionConfig:
        """Create streaming recognition configuration"""
        recognition_config = self.create_recognition_config(
            enable_diarization=enable_diarization,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        
        streaming_config = cloud_speech_types.StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=cloud_speech_types.StreamingRecognitionFeatures(
                interim_results=True,  # Get interim results for real-time display
                enable_voice_activity_events=True,
            ),
        )
        
        return streaming_config
    
    async def process_audio_chunk(
        self,
        audio_data: bytes,
        meeting_id: str,
        enable_diarization: bool = True,
    ) -> Dict:
        """
        Process a single audio chunk and return transcript with speaker info
        
        Args:
            audio_data: Raw audio bytes
            meeting_id: Meeting session ID
            enable_diarization: Whether to enable speaker diarization
            
        Returns:
            Dict with transcript, speaker, confidence, and timestamp
        """
        try:
            # Create streaming config
            streaming_config = self.create_streaming_config(
                enable_diarization=enable_diarization,
            )
            
            # Create initial config request
            config_request = cloud_speech_types.StreamingRecognizeRequest(
                recognizer=self.recognizer,
                streaming_config=streaming_config,
            )
            
            # Create audio request
            audio_request = cloud_speech_types.StreamingRecognizeRequest(
                audio=audio_data,
            )
            
            # Make streaming recognize request
            requests = [config_request, audio_request]
            responses = self.client.streaming_recognize(requests=requests)
            
            # Process responses
            results = []
            for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    
                    alternative = result.alternatives[0]
                    transcript = alternative.transcript
                    
                    # Extract speaker information if diarization is enabled
                    speaker_tag = None
                    if enable_diarization and alternative.words:
                        # Get speaker tag from first word (all words in same segment have same speaker)
                        speaker_tag = alternative.words[0].speaker_label if alternative.words else None
                    
                    results.append({
                        "transcript": transcript,
                        "speaker": f"Speaker {speaker_tag}" if speaker_tag else "Unknown",
                        "speaker_tag": speaker_tag,
                        "confidence": alternative.confidence if hasattr(alternative, 'confidence') else None,
                        "is_final": result.is_final,
                        "words": [
                            {
                                "word": word_info.word,
                                "start_time": word_info.start_offset.total_seconds() if word_info.start_offset else None,
                                "end_time": word_info.end_offset.total_seconds() if word_info.end_offset else None,
                                "speaker_tag": word_info.speaker_label if hasattr(word_info, 'speaker_label') else None,
                            }
                            for word_info in alternative.words
                        ] if alternative.words else [],
                    })
            
            # Return the most recent result (or combine all if needed)
            if results:
                # Prefer final results over interim
                final_results = [r for r in results if r["is_final"]]
                if final_results:
                    return final_results[-1]
                return results[-1]
            
            return {
                "transcript": "",
                "speaker": "Unknown",
                "speaker_tag": None,
                "confidence": None,
                "is_final": False,
                "words": [],
            }
            
        except Exception as e:
            print(f"Error processing audio chunk: {str(e)}")
            return {
                "transcript": "",
                "speaker": "Unknown",
                "speaker_tag": None,
                "confidence": None,
                "is_final": False,
                "error": str(e),
            }
    
    def start_streaming_session(
        self,
        meeting_id: str,
        enable_diarization: bool = True,
        min_speakers: int = 1,
        max_speakers: int = 10,
    ) -> str:
        """
        Start a new streaming session for continuous audio processing
        
        Returns:
            Session ID
        """
        session_id = f"{meeting_id}_stream"
        
        streaming_config = self.create_streaming_config(
            enable_diarization=enable_diarization,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        
        config_request = cloud_speech_types.StreamingRecognizeRequest(
            recognizer=self.recognizer,
            streaming_config=streaming_config,
        )
        
        # Store session info
        self.active_sessions[session_id] = {
            "meeting_id": meeting_id,
            "config_request": config_request,
            "enable_diarization": enable_diarization,
        }
        
        return session_id
    
    async def process_streaming_audio(
        self,
        session_id: str,
        audio_chunk: bytes,
    ) -> List[Dict]:
        """
        Process an audio chunk in an active streaming session
        
        Returns:
            List of transcript results
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        config_request = session["config_request"]
        
        # Create audio request
        audio_request = cloud_speech_types.StreamingRecognizeRequest(
            audio=audio_chunk,
        )
        
        # Make streaming request
        requests = [config_request, audio_request]
        responses = self.client.streaming_recognize(requests=requests)
        
        results = []
        for response in responses:
            for result in response.results:
                if not result.alternatives:
                    continue
                
                alternative = result.alternatives[0]
                transcript = alternative.transcript
                
                # Extract speaker information
                speaker_tag = None
                if session["enable_diarization"] and alternative.words:
                    speaker_tag = alternative.words[0].speaker_label if alternative.words else None
                
                results.append({
                    "transcript": transcript,
                    "speaker": f"Speaker {speaker_tag}" if speaker_tag else "Unknown",
                    "speaker_tag": speaker_tag,
                    "confidence": alternative.confidence if hasattr(alternative, 'confidence') else None,
                    "is_final": result.is_final,
                    "words": [
                        {
                            "word": word_info.word,
                            "start_time": word_info.start_offset.total_seconds() if word_info.start_offset else None,
                            "end_time": word_info.end_offset.total_seconds() if word_info.end_offset else None,
                            "speaker_tag": word_info.speaker_label if hasattr(word_info, 'speaker_label') else None,
                        }
                        for word_info in alternative.words
                    ] if alternative.words else [],
                })
        
        return results
    
    def stop_streaming_session(self, session_id: str):
        """Stop and clean up a streaming session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]


# Global instance
_stt_service: Optional[STTService] = None


def get_stt_service() -> STTService:
    """Get or create the global STT service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service

