# Junction2025 - Enterprise Meeting AR

An enterprise-focused AR application for Snapchat Spectacles that enhances meeting productivity through real-time AI-powered features including speech-to-text, meeting summarization, task extraction, and person identification.

## 🎯 Project Overview

This project provides an AR experience for enterprise meetings using Snapchat Spectacles glasses. The system captures audio and video in real-time, processes it through AI models, and displays contextual information directly in the user's field of view.

### Core Features

**Spectacles (AR Interface):**
- ✅ Start/Stop AI button for meeting control
- ✅ Real-time speech-to-text captions
- ✅ Live meeting summarization display
- ✅ Task extraction and display
- ✅ Person detection and identification
- ✅ Interactive UI with hand gesture controls (pinch, drag, hide)
- ✅ Settings page for customization

**Backend (AI Processing):**
- ✅ Speech-to-Text (STT) processing
- ✅ Speaker diarization (who said what)
- ✅ LLM-powered meeting summarization
- ✅ LLM-powered task extraction
- ✅ Meeting history storage
- ✅ Person identification

## 📁 Project Structure

```
Junction2025/
├── lens-studio/            # Snapchat Lens Studio project
│   ├── scripts/            # JavaScript scripts for AR experience
│   │   ├── controller.js   # Main controller (start/stop AI)
│   │   ├── api-client.js   # Backend API communication
│   │   ├── ui-manager.js   # UI element management
│   │   ├── captions.js     # Live captions/translations
│   │   ├── hand-tracking.js # Hand gesture interactions
│   │   └── settings.js     # Settings page
│   ├── resources/          # Assets, textures, materials
│   └── README.md           # Lens Studio setup guide
│
├── backend/                # FastAPI Python backend
│   ├── main.py            # FastAPI application with API endpoints
│   ├── requirements.txt   # Python dependencies
│   ├── Dockerfile         # Docker configuration
│   ├── docker-compose.yml # Docker Compose setup
│   └── README.md          # Backend documentation
│
├── core/                   # Shared utilities and types
│   ├── types/             # Shared TypeScript types
│   └── constants/         # Shared constants
│
├── documents/              # Project documentation
│   ├── projects/          # Project specifications
│   └── benefits/          # Project benefits
│
└── ml_model_tests/        # ML model testing files
    └── speech-to-text/    # STT model tests
```

## 🚀 Quick Start

### Prerequisites

- **Lens Studio** - [Download](https://lensstudio.snapchat.com/) (for AR development)
- **Python 3.11+** - For backend development
- **Docker & Docker Compose** - For backend deployment
- **Snapchat Spectacles** - For testing (or use Lens Studio preview)

### 1. Backend Setup

The backend handles all AI processing and provides the API for the Spectacles app.

#### Using Docker Compose (Recommended)

```bash
cd backend
docker compose up --build
```

The backend API will be available at `http://localhost:8000`

#### Local Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 2. Lens Studio Setup

1. **Install Lens Studio:**
   - Download from [Snap Lens Studio](https://lensstudio.snapchat.com/)
   - Install and launch

2. **Open Project:**
   - File → Open Project → Select `lens-studio/` directory
   - Or create a new project and copy the scripts

3. **Configure Backend URL:**
   - Edit `lens-studio/scripts/api-client.js`
   - Update `API_BASE_URL` if your backend is not at `http://localhost:8000`

4. **Test Connection:**
   - Ensure backend is running
   - Use the start/stop button in the Lens to test API connection

## 🏗️ Architecture

### System Flow

```
Spectacles (Lens Studio)
    ↓ [Audio/Video Capture]
    ↓ [HTTP/WebSocket]
Backend API (FastAPI)
    ↓ [STT Processing]
    ↓ [Speaker Diarization]
    ↓ [LLM Summarization]
    ↓ [Task Extraction]
    ↓ [Person Detection]
    ↑ [JSON Response]
Spectacles (Display UI)
```

### API Endpoints

**Meetings:**
- `POST /api/meetings/start` - Start a new meeting
- `POST /api/meetings/{id}/stop` - Stop a meeting
- `GET /api/meetings` - Get meeting history
- `GET /api/meetings/{id}` - Get meeting details
- `GET /api/meetings/{id}/summary` - Get real-time summary

**Audio/STT:**
- `POST /api/audio/stream` - Stream audio for STT processing

**Tasks:**
- `GET /api/meetings/{id}/tasks` - Get extracted tasks
- `POST /api/meetings/{id}/tasks` - Add task manually

**Person Detection:**
- `POST /api/persons/detect` - Detect and identify person

## 🎮 Features in Detail

### 1. Start/Stop Button
- **Location:** AR space (configurable position)
- **Function:** Toggles AI processing on/off
- **Visual Feedback:** Changes appearance based on state

### 2. Live Captions
- **Display:** Real-time speech-to-text transcription
- **Features:**
  - Speaker identification
  - Translation support (optional)
  - Scrollable history
- **Interaction:** Pinch to move, swipe to hide

### 3. Meeting Summarization
- **Display:** Periodic meeting summaries
- **Updates:** Real-time as meeting progresses
- **Content:** Key points, decisions, action items
- **Interaction:** Full gesture support

### 4. Tasks Display
- **Display:** Extracted tasks from meetings
- **Features:**
  - Due dates
  - Task status
  - Auto-extracted from conversation
- **Interaction:** Pinch to move, tap to expand

### 5. Hand Gesture Interactions
- **Pinch:** Select and move UI elements
- **Drag:** Reposition elements in AR space
- **Swipe:** Hide/show elements
- **Tap:** Interact with buttons/controls

### 6. Settings Page
- **Access:** Gesture-based menu
- **Options:**
  - Toggle captions/translations
  - Adjust UI positions
  - Configure API endpoint
  - Update preferences

## 🔧 Development

### Backend Development

The backend uses FastAPI and includes placeholder endpoints for:
- STT processing (integrate your STT model)
- Speaker diarization (integrate diarization model)
- LLM summarization (integrate OpenAI/Anthropic/etc.)
- Task extraction (integrate LLM for task detection)
- Person detection (integrate face recognition model)

**Current Status:**
- ✅ API structure and endpoints
- ✅ Meeting session management
- ⏳ STT integration (TODO)
- ⏳ Speaker diarization (TODO)
- ⏳ LLM integration (TODO)
- ⏳ Person detection (TODO)

### Lens Studio Development

**Scripts Overview:**
- `controller.js` - Main application controller
- `api-client.js` - Backend communication
- `ui-manager.js` - UI element management
- `captions.js` - Caption display logic
- `hand-tracking.js` - Gesture recognition
- `settings.js` - Settings management

**Testing:**
- Use Lens Studio preview mode
- Test with webcam/microphone
- Use hand tracking simulation
- Check backend logs for API calls

## 📊 API Documentation

Once the backend is running, visit:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## 🔐 Environment Variables

### Backend

Create a `.env` file in `backend/`:

```env
API_HOST=0.0.0.0
API_PORT=8000
# Add your API keys for STT, LLM, etc.
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here
```

## 🚢 Deployment

### Backend

1. **Build Docker image:**
   ```bash
   cd backend
   docker build -t junction2025-backend .
   ```

2. **Deploy to production:**
   - Update CORS origins in `main.py`
   - Set environment variables
   - Deploy container to your hosting service

### Lens Studio

1. **Export Lens:**
   - File → Export Lens in Lens Studio
   - Follow Snapchat's submission process

2. **Update API URL:**
   - Edit `lens-studio/scripts/api-client.js`
   - Set `API_BASE_URL` to production endpoint

## 🧪 Testing

### Backend API Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Start a meeting
curl -X POST http://localhost:8000/api/meetings/start

# Get meeting summary
curl http://localhost:8000/api/meetings/{meeting_id}/summary
```

### Lens Studio Testing

1. Open project in Lens Studio
2. Use preview mode
3. Test with webcam/microphone
4. Verify API calls in backend logs

## 📝 TODO / Future Development

### Backend
- [ ] Integrate STT model (Whisper, Google Speech-to-Text, etc.)
- [ ] Implement speaker diarization
- [ ] Integrate LLM for summarization (OpenAI, Anthropic, etc.)
- [ ] Implement task extraction with LLM
- [ ] Add person detection/identification
- [ ] Database integration (replace in-memory storage)
- [ ] WebSocket support for real-time updates
- [ ] Authentication and user management

### Lens Studio
- [ ] Complete UI element implementation
- [ ] Audio capture integration
- [ ] Hand gesture refinement
- [ ] Settings page UI
- [ ] Visual polish and animations
- [ ] Performance optimization

## 🐛 Troubleshooting

### Backend Issues
- **Port 8000 already in use:** Change port in `docker-compose.yml` or `main.py`
- **CORS errors:** Backend allows all origins by default
- **Docker build fails:** Ensure Docker is running and has sufficient resources

### Lens Studio Issues
- **API connection fails:** Check backend is running and URL is correct
- **Hand tracking not working:** Ensure Hand Tracking component is added to scene
- **Audio not capturing:** Check microphone permissions and Lens Studio audio settings

## 📚 Resources

- [Lens Studio Documentation](https://docs.snap.com/lens-studio/)
- [Lens Studio Scripting API](https://docs.snap.com/lens-studio/references/guides/scripting-overview)
- [Hand Tracking Guide](https://docs.snap.com/lens-studio/references/guides/input/hand-tracking)
- [Spectacles Development](https://docs.snap.com/spectacles/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 📄 License

[Add your license information here]

## 👥 Team

Junction 2025 Hackathon Team

---

**Built for Junction 2025 Hackathon - Snapchat Spectacles Challenge**
