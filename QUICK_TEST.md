# Quick Test Guide - Audio Streaming

## Step-by-Step Testing

### Step 1: Install Dependencies (if needed)

```bash
pip install pyaudio websockets httpx
```

**If pyaudio fails on macOS:**
```bash
brew install portaudio
pip install pyaudio
```

### Step 2: Start Backend Server

Open **Terminal 1**:
```bash
cd backend
python main.py
```

Wait until you see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ Backend is ready!

### Step 3: Run Test Script

Open **Terminal 2** (new terminal window):
```bash
# Make sure you're in project root
cd /Users/duartecruz/Desktop/junctionX\ hackathon/finlandia/project/Junction2025

# Run test
python3 test_audio_streaming.py
```

### Step 4: Test!

1. **Script will start:**
   - Creates a meeting automatically
   - Connects to WebSocket
   - Starts listening to microphone

2. **Speak into your microphone:**
   - Say something like: "Hello, this is a test"
   - Wait a moment (processing takes 1-3 seconds)
   - You should see transcriptions appear!

3. **Expected output:**
   ```
   🎤 Speaker 1: Hello, this is a test
   ```

4. **Stop:**
   - Press `Ctrl+C` to stop

## Troubleshooting

### "ModuleNotFoundError: No module named 'pyaudio'"
```bash
pip install pyaudio
# Or on macOS:
brew install portaudio && pip install pyaudio
```

### "Could not start meeting"
- Check Terminal 1 - is backend running?
- Look for errors in backend console
- Make sure `.env` has `OPENAI_API_KEY`

### "WebSocket connection failed"
- Backend must be running first!
- Check Terminal 1 for errors
- Verify port 8000 is not in use

### "No transcriptions appearing"
- Wait 2-3 seconds after speaking
- Check backend logs (Terminal 1) for errors
- Verify OpenAI API key is valid
- Speak clearly and loudly

### "No audio captured"
- Check microphone permissions
- macOS: System Settings → Privacy → Microphone
- Make sure microphone is not muted
- Try speaking louder

## What Success Looks Like

✅ Backend running on port 8000  
✅ Test script connects successfully  
✅ Microphone captures audio  
✅ Transcriptions appear after speaking  
✅ Multiple sentences work  
✅ Can stop cleanly with Ctrl+C  

## Next Steps After Testing

Once this works:
1. ✅ Backend is working
2. ✅ WebSocket streaming works
3. ✅ OpenAI transcription works
4. ✅ Ready for Lens Studio testing!

