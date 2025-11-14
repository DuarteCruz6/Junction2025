# Next Steps - STT Implementation

## ✅ Step 1: Backend Setup

### 1.1 Install Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1.2 Configure Environment Variables
Create/update `backend/.env` file:
```env
# REQUIRED for STT
OPENAI_API_KEY=sk-your-api-key-here

# OPTIONAL: Database (for persistent storage)
# DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**Get OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy it to your `.env` file

### 1.3 Start Backend Server
```bash
# Make sure you're in the backend directory with venv activated
python main.py
```

Or with uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Verify it's running:**
- Open http://localhost:8000/docs (Swagger UI)
- You should see the API documentation

---

## ✅ Step 2: Lens Studio Setup

### 2.1 Open Lens Studio Project
1. Launch **Lens Studio**
2. Open your project (or create new project)
3. Navigate to the `lens-studio/` folder in this project

### 2.2 Add Audio Component
1. In Lens Studio, select your **Main Camera** or create a new entity
2. Add **Audio Component**:
   - Right-click entity → **Add Component** → **Audio Component**
3. Add **MicrophoneAudioProvider**:
   - With Audio Component selected, in Inspector panel:
   - Click **+ Add Component** → **MicrophoneAudioProvider**

### 2.3 Configure Scripts
1. **Add Scripts to Scene:**
   - Add `api-client.js` script to an entity
   - Add `captions.js` script to an entity
   - Add `controller.js` script to an entity

2. **Link Scripts:**
   - In `captions.js` script component:
     - Set `@input Component.ScriptComponent apiClientScript` → point to entity with `api-client.js`
     - Set `@input Component.AudioComponent audioComponent` → point to entity with Audio Component

3. **Update API URL (if needed):**
   - Open `lens-studio/scripts/api-client.js`
   - Line 8: Update `API_BASE_URL` if your backend is not on `localhost:8000`
   - For production: Change to your server URL

---

## ✅ Step 3: Test the Implementation

### 3.1 Test Backend (Without Lens Studio)
```bash
# Start a meeting
curl -X POST http://localhost:8000/api/meetings/start

# Response will include a meeting_id
# Save this meeting_id for next step
```

### 3.2 Test Audio WebSocket (Optional)
You can test the WebSocket endpoint using a tool like:
- **Postman** (has WebSocket support)
- **wscat** (command line): `npm install -g wscat`
  ```bash
  wscat -c ws://localhost:8000/ws/audio/{meeting_id}
  ```

### 3.3 Test in Lens Studio
1. **Start Preview:**
   - Click the **Preview** button in Lens Studio
   - Or press `Space` to start preview

2. **Enable Microphone:**
   - In Preview panel, click the **microphone icon** at the bottom
   - Grant microphone permissions when prompted

3. **Start Meeting:**
   - Use your start/stop button in the Lens
   - Or trigger `controller.js` start function

4. **Speak:**
   - Speak into your microphone
   - Check backend console for logs:
     - Should see "Audio WebSocket connected"
     - Should see "Audio chunk received"
     - Should see transcription results

5. **Check Captions:**
   - Captions should appear in the Lens preview
   - Transcripts should update in real-time

---

## ✅ Step 4: Troubleshooting

### Backend Issues

**Problem: "OpenAI API key not found"**
- Check `.env` file exists in `backend/` directory
- Verify `OPENAI_API_KEY=sk-...` is set correctly
- Restart the server after adding env vars

**Problem: "WebSocket connection failed"**
- Check backend is running on port 8000
- Check CORS settings (should allow all origins)
- Verify meeting ID is valid

**Problem: "No transcription results"**
- Check OpenAI API key is valid
- Check backend logs for errors
- Verify audio format is correct (PCM 16kHz mono)

### Lens Studio Issues

**Problem: "MicrophoneAudioProvider not found"**
- Verify you added MicrophoneAudioProvider component
- Check script inputs are linked correctly
- Try restarting Lens Studio

**Problem: "No audio captured"**
- Check microphone permissions in Lens Studio
- Click microphone icon in Preview panel
- Check console for error messages

**Problem: "WebSocket not connecting"**
- Verify `API_BASE_URL` in `api-client.js` is correct
- Check backend is accessible from your machine
- For Spectacles: May need to use IP address instead of `localhost`

**Problem: "Words being cut off"**
- Adjust VAD settings in `captions.js`:
  - Line 31: `energyThreshold` - increase if too sensitive
  - Line 32: `minSilenceDuration` - increase for longer pauses
  - Line 33: `minSpeechDuration` - decrease to detect speech faster

---

## ✅ Step 5: Calibration (Optional but Recommended)

### Calibrate VAD Settings
The Voice Activity Detection may need tuning for your environment:

1. **Test in your environment:**
   - Speak normally
   - Speak quietly
   - Test with background noise

2. **Adjust in `captions.js` (line 27-36):**
   ```javascript
   let vadState = {
       energyThreshold: 0.01,      // Increase if too sensitive to noise
       minSilenceDuration: 0.5,    // Increase if cutting words
       minSpeechDuration: 0.3,      // Decrease to detect speech faster
       maxChunkDuration: 3.0,       // Max time before forcing send
   };
   ```

3. **Fine-tune:**
   - If words cut off → increase `minSilenceDuration`
   - If too much noise → increase `energyThreshold`
   - If slow to start → decrease `minSpeechDuration`

---

## ✅ Step 6: Production Deployment (When Ready)

### Backend
1. Deploy to cloud (Heroku, Railway, AWS, etc.)
2. Update `API_BASE_URL` in Lens Studio scripts
3. Set environment variables on hosting platform
4. Enable HTTPS (required for WebSocket in production)

### Lens Studio
1. Export Lens: **File → Export Lens**
2. Submit to Snapchat (if publishing)
3. Update API URL to production endpoint

---

## Quick Checklist

- [ ] Backend dependencies installed
- [ ] `.env` file created with `OPENAI_API_KEY`
- [ ] Backend server running on port 8000
- [ ] Lens Studio project opened
- [ ] Audio Component + MicrophoneAudioProvider added
- [ ] Scripts added and linked correctly
- [ ] Microphone permissions granted
- [ ] Meeting started in Lens
- [ ] Audio streaming (check backend logs)
- [ ] Transcriptions appearing
- [ ] Captions displaying in Lens

---

## Need Help?

- Check `STT_IMPLEMENTATION.md` for detailed documentation
- Check backend logs for errors
- Check Lens Studio console (View → Console)
- Verify all components are linked correctly

Good luck! 🚀

