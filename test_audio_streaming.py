#!/usr/bin/env python3
"""
Test script for audio streaming to backend
Captures audio from computer microphone and streams to WebSocket endpoint

Requirements:
    pip install pyaudio websockets httpx

Usage:
    python test_audio_streaming.py
"""

import pyaudio
import asyncio
import websockets
import json
import sys
from datetime import datetime

try:
    import httpx
except ImportError:
    print("❌ Missing dependency: httpx")
    print("   Install with: pip install httpx")
    sys.exit(1)

# Configuration
BACKEND_URL = "ws://localhost:8000"
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1600  # ~100ms at 16kHz (16000 * 0.1 * 1 channel * 2 bytes)
FORMAT = pyaudio.paInt16

# VAD Configuration (simple energy-based) - optimized for lower latency
ENERGY_THRESHOLD = 0.005  # Lowered for better detection
MIN_SILENCE_DURATION = 0.3  # seconds (reduced for faster chunk sending)
MIN_SPEECH_DURATION = 0.15   # seconds (lowered for faster detection)
MAX_CHUNK_DURATION = 1.5    # seconds (reduced from 3.0 for lower latency)

# Debug mode
DEBUG = True  # Set to True to see energy levels and VAD state

class AudioStreamer:
    def __init__(self, meeting_id: str):
        self.meeting_id = meeting_id
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.websocket = None
        self.audio_buffer = []
        self.vad_state = {
            "is_speech": False,
            "silence_duration": 0.0,
            "speech_duration": 0.0,
        }
        
    def calculate_energy(self, audio_data: bytes) -> float:
        """Calculate RMS energy of audio chunk"""
        import struct
        samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
        sum_squares = sum(sample * sample for sample in samples)
        rms = (sum_squares / len(samples)) ** 0.5
        return rms / 32768.0  # Normalize to 0-1 range
    
    async def connect_websocket(self):
        """Connect to audio streaming WebSocket"""
        ws_url = f"{BACKEND_URL}/ws/audio/{self.meeting_id}"
        print(f"Connecting to {ws_url}...")
        
        try:
            self.websocket = await websockets.connect(ws_url)
            print("✅ WebSocket connected!")
            
            # Wait for connection confirmation
            response = await self.websocket.recv()
            message = json.loads(response)
            if message.get("type") == "connected":
                print(f"✅ {message['data']['message']}")
                return True
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False
    
    async def handle_messages(self):
        """Handle incoming WebSocket messages"""
        print("\n📡 Message handler started, waiting for messages...")
        try:
            while True:
                message = await self.websocket.recv()
                print(f"\n📥 Raw message received (type: {type(message).__name__}, length: {len(message) if isinstance(message, (str, bytes)) else 'N/A'})")
                
                # Handle both text (JSON) and binary messages
                if isinstance(message, bytes):
                    if DEBUG:
                        print(f"\n📦 Received binary message ({len(message)} bytes)")
                    continue
                
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    if DEBUG:
                        print(f"\n⚠️  Received non-JSON message: {message[:100]}")
                    continue
                
                msg_type = data.get("type")
                if DEBUG:
                    print(f"\n📨 Received message type: {msg_type}")
                
                if msg_type == "transcription_result":
                    segments = data.get("data", {}).get("segments", [])
                    full_text = data.get("data", {}).get("full_text", "")
                    
                    if segments:
                        print(f"\n{'='*60}")
                        print("📝 TRANSCRIPTION RESULT:")
                        for segment in segments:
                            speaker = segment.get("speaker", "Unknown")
                            text = segment.get("text", "")
                            print(f"🎤 {speaker}: {text}")
                        print(f"{'='*60}\n")
                    elif full_text:
                        print(f"\n{'='*60}")
                        print(f"📝 TRANSCRIPTION: {full_text}")
                        print(f"{'='*60}\n")
                    else:
                        print(f"\n⚠️  Transcription result with no segments or text")
                
                elif msg_type == "transcription_error":
                    error = data.get("data", {}).get("error", "Unknown error")
                    print(f"\n❌ Transcription error: {error}")
                
                elif msg_type == "audio_received":
                    duration = data.get("data", {}).get("buffer_duration", 0)
                    status = data.get("data", {}).get("status", "unknown")
                    print(f"\n✅ Backend received audio ({duration:.2f}s), status: {status}")
                
                elif msg_type == "connected":
                    print(f"\n✅ {data.get('data', {}).get('message', 'Connected')}")
                
                elif msg_type == "error":
                    error = data.get("data", {}).get("error", "Unknown error")
                    print(f"\n❌ Backend error: {error}")
                
                else:
                    if DEBUG:
                        print(f"\n⚠️  Unknown message type: {msg_type}")
                        print(f"   Data: {str(data)[:200]}")
        except websockets.exceptions.ConnectionClosed:
            print("\n⚠️  WebSocket connection closed")
        except Exception as e:
            print(f"\n❌ Error handling messages: {e}")
            import traceback
            traceback.print_exc()
    
    def start_audio_stream(self):
        """Start capturing audio from microphone"""
        self.stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        print("🎙️  Microphone ready. Start speaking...")
        print("   (Press Ctrl+C to stop)\n")
    
    async def process_audio_chunk(self, chunk: bytes):
        """Process audio chunk with VAD"""
        # Calculate energy
        energy = self.calculate_energy(chunk)
        is_speech = energy > ENERGY_THRESHOLD
        
        chunk_duration = CHUNK_SIZE / SAMPLE_RATE
        
        # Debug output
        if DEBUG:
            status = "🎤 SPEECH" if is_speech else "🔇 silence"
            print(f"\r{status} | Energy: {energy:.4f} | Buffer: {len(self.audio_buffer)} chunks", end="", flush=True)
        
        # VAD State Machine
        if is_speech:
            self.vad_state["speech_duration"] += chunk_duration
            self.vad_state["silence_duration"] = 0.0
            
            if not self.vad_state["is_speech"]:
                if self.vad_state["speech_duration"] >= MIN_SPEECH_DURATION:
                    self.vad_state["is_speech"] = True
                    if DEBUG:
                        print(f"\n✅ Speech detected! Starting to buffer...")
        else:
            self.vad_state["silence_duration"] += chunk_duration
            self.vad_state["speech_duration"] = 0.0
            
            if self.vad_state["is_speech"]:
                if self.vad_state["silence_duration"] >= MIN_SILENCE_DURATION:
                    # End of speech - send chunk
                    if DEBUG:
                        print(f"\n📤 Sending audio chunk (silence detected)...")
                    await self.send_audio_chunk(is_final=True)
                    self.vad_state["is_speech"] = False
                    self.vad_state["silence_duration"] = 0.0
                    return
        
        # Add to buffer
        self.audio_buffer.append(chunk)
        
        # Calculate buffer duration
        buffer_duration = (len(self.audio_buffer) * CHUNK_SIZE) / SAMPLE_RATE
        
        # Send if max duration reached
        if self.vad_state["is_speech"] and buffer_duration >= MAX_CHUNK_DURATION:
            if DEBUG:
                print(f"\n📤 Sending audio chunk (max duration reached)...")
            await self.send_audio_chunk(is_final=False)
    
    async def send_audio_chunk(self, is_final: bool = False):
        """Send buffered audio chunks via WebSocket"""
        if not self.audio_buffer:
            if DEBUG:
                print("\n⚠️  No audio in buffer to send")
            return
        
        if not self.websocket:
            if DEBUG:
                print("\n⚠️  WebSocket not connected")
            return
        
        try:
            # Combine all buffered chunks
            combined = b''.join(self.audio_buffer)
            duration = len(combined) / (SAMPLE_RATE * 2)  # 2 bytes per sample
            
            if DEBUG:
                print(f"\n📤 Sending {len(self.audio_buffer)} chunks ({duration:.2f}s) to backend...")
            
            # Send binary data
            await self.websocket.send(combined)
            
            # Clear buffer
            self.audio_buffer = []
            
            if DEBUG:
                print("✅ Audio sent, waiting for transcription...")
            
        except Exception as e:
            print(f"\n❌ Error sending audio: {e}")
            import traceback
            traceback.print_exc()
    
    async def stream_audio(self):
        """Main audio streaming loop"""
        if not self.stream:
            self.start_audio_stream()
        
        try:
            while True:
                # Read audio chunk
                chunk = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Process with VAD
                await self.process_audio_chunk(chunk)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping...")
        finally:
            # Send final chunk
            if self.audio_buffer:
                await self.send_audio_chunk(is_final=True)
            
            # Send end stream message
            if self.websocket:
                await self.websocket.send(json.dumps({"type": "end_stream"}))
    
    async def run(self):
        """Run the audio streaming test"""
        # Connect WebSocket
        if not await self.connect_websocket():
            return
        
        # Start message handler in background
        message_task = asyncio.create_task(self.handle_messages())
        
        # Start audio streaming
        try:
            await self.stream_audio()
        finally:
            # Cleanup
            message_task.cancel()
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio:
                self.audio.terminate()
            if self.websocket:
                await self.websocket.close()
            print("✅ Cleanup complete")


async def start_meeting() -> str:
    """Start a meeting and return meeting_id"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL.replace('ws://', 'http://')}/api/meetings/start")
            if response.status_code == 200:
                data = response.json()
                return data.get("meeting_id")
            else:
                print(f"❌ Failed to start meeting: {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ Error starting meeting: {e}")
        return None


async def main():
    print("=" * 60)
    print("🎤 Audio Streaming Test - Computer Microphone")
    print("=" * 60)
    print()
    
    # Start a meeting
    print("📞 Starting meeting...")
    meeting_id = await start_meeting()
    
    if not meeting_id:
        print("❌ Could not start meeting. Is the backend running?")
        print("   Make sure to run: python backend/main.py")
        sys.exit(1)
    
    print(f"✅ Meeting started: {meeting_id}")
    print()
    
    # Create and run audio streamer
    streamer = AudioStreamer(meeting_id)
    await streamer.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

