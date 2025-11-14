# STT Implementation Guide

## Overview
This document describes the Speech-to-Text (STT) implementation for Snapchat Spectacles glasses using OpenAI's transcription API with real-time streaming.

## Architecture

### Backend Components

1. **STT Service** (`backend/services/stt_service.py`)
   - Handles audio buffering and transcription
   - Buffers audio chunks (0.5s - 3s) before processing
   - Converts PCM audio to WAV format for OpenAI API
   - Supports speaker diarization via OpenAI's `gpt-4o-transcribe-diarize` model

2. **WebSocket Audio Endpoint** (`backend/api/routes/websocket.py`)
   - New endpoint: `/ws/audio/{meeting_id}`
   - Receives binary PCM audio chunks via WebSocket
   - Processes audio in buffers and sends transcriptions back
   - Broadcasts transcript updates to all meeting participants

3. **Audio Buffering Strategy**
   - **Minimum buffer**: 0.5 seconds (prevents too many API calls)
   - **Maximum buffer**: 3 seconds (ensures low latency)
   - **Processing trigger**: When buffer reaches min duration OR max duration OR final chunk

### Lens Studio Components

1. **API Client** (`lens-studio/scripts/api-client.js`)
   - WebSocket connection management
   - Automatic connection on meeting start
   - Handles transcription result callbacks

2. **Captions Script** (`lens-studio/scripts/captions.js`)
   - Audio capture using `MicrophoneAudioProvider`
   - Voice Activity Detection (VAD) for smart chunking
   - Sends audio chunks via WebSocket

## Voice Activity Detection (VAD)

The VAD implementation uses energy-based detection:

- **Energy Threshold**: 0.01 (adjustable based on testing)
- **Min Silence Duration**: 0.5 seconds (to end a chunk)
- **Min Speech Duration**: 0.3 seconds (to start a chunk)
- **Max Chunk Duration**: 3.0 seconds (force send to prevent latency)

### VAD State Machine

1. **Silence → Speech**: When energy > threshold for 300ms
2. **Speech → Silence**: When energy < threshold for 500ms (sends chunk)
3. **Force Send**: If buffer reaches 3 seconds during speech

This ensures words are not cut off mid-sentence.

## Audio Format

- **Sample Rate**: 16 kHz (standard for speech)
- **Channels**: Mono (1 channel)
- **Bit Depth**: 16-bit (2 bytes per sample)
- **Format**: PCM → WAV (converted on backend)

## Setup Instructions

### Backend

1. Ensure OpenAI API key is set in `.env`:
   ```
   OPENAI_API_KEY=your_key_here
   ```

2. Start the backend:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

### Lens Studio

1. **Add MicrophoneAudioProvider**:
   - In Lens Studio, add an `AudioComponent` to your scene
   - Add a `MicrophoneAudioProvider` component to it
   - Configure the audio component in the `captions.js` script input

2. **Configure API URL**:
   - Edit `lens-studio/scripts/api-client.js`
   - Update `API_BASE_URL` if needed (default: `http://localhost:8000`)

3. **Test Audio Capture**:
   - Start a meeting in the Lens
   - Audio should automatically start streaming
   - Check backend logs for transcription results

## Important Notes

### Lens Studio API Considerations

The implementation assumes `MicrophoneAudioProvider` has:
- `getAudioBuffer()` method that returns audio samples
- `enabled` property to start/stop capture

**If the API differs**, you may need to adjust:
- `captions.js` lines 58-68: How to get the MicrophoneAudioProvider
- `captions.js` line 123: How to get audio data (`getAudioBuffer()`)

### WebSocket Support

Lens Studio's JavaScript environment should support WebSocket. If not available:
- Fall back to HTTP POST method (see `sendAudioChunkHTTP()` in api-client.js)
- Note: HTTP has higher latency and overhead

### Rate Limits

Lens Studio has rate limits:
- **Payload size**: 100KB per message
- **Rate limit**: 250 requests per 5 seconds

Our implementation respects these by:
- Sending chunks only when VAD detects speech boundaries
- Buffering to reduce message frequency
- Using binary WebSocket (more efficient than base64)

## Testing

1. **Test Audio Capture**:
   - Start meeting in Lens Studio
   - Speak into microphone
   - Check backend logs for audio chunks received

2. **Test Transcription**:
   - Verify transcriptions appear in WebSocket messages
   - Check captions update in real-time

3. **Test VAD**:
   - Speak with pauses
   - Verify chunks are sent at natural boundaries
   - Ensure words are not cut off

## Troubleshooting

### No Audio Captured
- Check microphone permissions in Lens Studio
- Verify `MicrophoneAudioProvider` is added to scene
- Check console for error messages

### WebSocket Connection Failed
- Verify backend is running
- Check CORS settings (should allow all origins)
- Verify meeting ID is valid

### Transcription Not Working
- Check OpenAI API key is set
- Verify audio format is correct (PCM 16kHz mono)
- Check backend logs for errors

### Words Being Cut Off
- Adjust `minSilenceDuration` in `vadState` (increase for longer pauses)
- Adjust `energyThreshold` (may need calibration for your environment)

## Future Improvements

1. **Adaptive VAD**: Adjust energy threshold based on ambient noise
2. **Multiple Language Support**: Detect and transcribe multiple languages
3. **Real-time Translation**: Add translation alongside transcription
4. **Speaker Identification**: Improve speaker diarization accuracy
5. **Offline Mode**: Cache audio when connection is lost

