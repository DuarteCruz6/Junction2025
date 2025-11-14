# Testing Audio Streaming with Computer Microphone

This guide shows you how to test the STT implementation using your computer's microphone before testing on Spectacles glasses.

## Quick Start

### 1. Install Dependencies

```bash
# Make sure you're in the project root
pip install pyaudio websockets httpx
```

**Note for macOS:**
```bash
# If pyaudio installation fails, install portaudio first:
brew install portaudio
pip install pyaudio
```

**Note for Linux:**
```bash
# Install system dependencies first:
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

**Note for Windows:**
```bash
# Usually works directly:
pip install pyaudio
```

### 2. Start Backend Server

In one terminal:
```bash
cd backend
python main.py
```

Make sure:
- ✅ Backend is running on `http://localhost:8000`
- ✅ `.env` file has `OPENAI_API_KEY` set

### 3. Run Test Script

In another terminal:
```bash
# From project root
python test_audio_streaming.py
```

## What to Expect

1. **Script starts:**
   ```
   ============================================================
   🎤 Audio Streaming Test - Computer Microphone
   ============================================================
   
   📞 Starting meeting...
   ✅ Meeting started: abc-123-def-456
   
   Connecting to ws://localhost:8000/ws/audio/abc-123-def-456...
   ✅ WebSocket connected!
   ✅ Audio streaming ready
   🎙️  Microphone ready. Start speaking...
      (Press Ctrl+C to stop)
   ```

2. **Speak into your microphone:**
   - The script uses VAD (Voice Activity Detection)
   - It will detect when you start/stop speaking
   - Audio chunks are sent automatically

3. **See transcriptions:**
   ```
   📤 Audio chunk sent (1.23s)
   🎤 Speaker 1: Hello, this is a test
   🎤 Speaker 2: How are you doing?
   ```

4. **Stop:**
   - Press `Ctrl+C` to stop
   - Final audio chunk will be sent
   - Connection will close cleanly

## Troubleshooting

### "No module named 'pyaudio'"
```bash
pip install pyaudio
# Or on macOS:
brew install portaudio && pip install pyaudio
```

### "No module named 'websockets'"
```bash
pip install websockets
```

### "No module named 'httpx'"
```bash
pip install httpx
```

### "Could not start meeting"
- Check backend is running: `python backend/main.py`
- Check backend is on port 8000
- Check `.env` file exists with `OPENAI_API_KEY`

### "WebSocket connection failed"
- Verify backend is running
- Check URL is correct (default: `ws://localhost:8000`)
- Check backend logs for errors

### "No audio captured"
- Check microphone permissions
- On macOS: System Settings → Privacy → Microphone
- Try speaking louder
- Check microphone is not muted

### "No transcriptions appearing"
- Check OpenAI API key is valid
- Check backend logs for errors
- Verify you're speaking clearly
- Wait a few seconds (processing takes time)

## Adjusting VAD Settings

If words are being cut off or too much silence is captured, edit `test_audio_streaming.py`:

```python
# Line ~20-25
ENERGY_THRESHOLD = 0.01        # Increase if too sensitive to noise
MIN_SILENCE_DURATION = 0.5    # Increase if cutting words
MIN_SPEECH_DURATION = 0.3      # Decrease to detect speech faster
MAX_CHUNK_DURATION = 3.0       # Max time before forcing send
```

## Testing Different Scenarios

### Test 1: Single Speaker
- Speak normally
- Pause between sentences
- Verify chunks are sent at natural pauses

### Test 2: Multiple Speakers (Simulated)
- Speak, pause, speak again
- OpenAI diarization should identify different segments
- May show as "Speaker 1", "Speaker 2", etc.

### Test 3: Background Noise
- Test with background noise
- Adjust `ENERGY_THRESHOLD` if needed
- Should filter out low-energy noise

### Test 4: Long Speech
- Speak continuously for 10+ seconds
- Should send chunks every ~3 seconds (MAX_CHUNK_DURATION)
- Verify no words are lost

## Next Steps

Once this works:
1. ✅ Backend is working correctly
2. ✅ WebSocket streaming is functional
3. ✅ VAD is detecting speech properly
4. ✅ OpenAI transcription is working

Then you can:
- Test in Lens Studio with Spectacles
- Adjust VAD settings based on your environment
- Deploy to production

## Comparison with Lens Studio

This test script mimics what Lens Studio does:
- ✅ Captures audio from microphone
- ✅ Uses VAD for smart chunking
- ✅ Sends via WebSocket
- ✅ Receives transcriptions

The main difference:
- **This script**: Uses `pyaudio` (Python)
- **Lens Studio**: Uses `MicrophoneAudioProvider` (JavaScript)

But the backend and WebSocket protocol are identical!

