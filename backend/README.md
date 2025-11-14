# Backend

This folder contains the Python FastAPI backend application that serves as the API layer for the Enterprise Meeting AR application.

## Purpose

The backend handles:
- **Speech-to-Text (STT)**: OpenAI Whisper API with speaker diarization
- **LLM Processing**: GPT-4o-mini for meeting summarization and task extraction
- **Real-time Updates**: WebSocket support for live transcript, summary, and task updates
- **Meeting Management**: Start/stop meetings, store history, manage tasks
- **Speaker Recognition**: Register known speakers for better diarization

## Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── services/                  # Service modules
│   ├── stt_service.py        # Speech-to-text with diarization
│   ├── llm_service.py        # LLM for summarization & tasks
│   └── websocket_manager.py  # WebSocket connection management
├── models/                    # Database models
│   └── database.py           # SQLAlchemy models and DB setup
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose configuration
└── .env.example              # Environment variables template
```

## Technology Stack

- **Framework:** FastAPI
- **Language:** Python 3.11+
- **Server:** Uvicorn
- **STT:** OpenAI Whisper API (with speaker diarization)
- **LLM:** GPT-4o-mini (OpenAI)
- **Real-time:** WebSocket support
- **Database:** Supabase (PostgreSQL) - recommended for Spectacles integration
- **Containerization:** Docker

## Running the Backend

### Using Docker (Recommended)

```bash
docker-compose up --build
```

### Local Development

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The API will be available at `http://localhost:8000`
API documentation (Swagger UI) is available at `http://localhost:8000/docs`

## Environment Variables

Create a `.env` file in this directory (see `.env.example` for template):

**Required:**
```env
OPENAI_API_KEY=your_openai_api_key_here
```

**Optional:**
```env
# Supabase Database (recommended for Spectacles integration)
# Get connection string from Supabase Dashboard > Settings > Database
# Use connection pooler (port 6543) for better performance:
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Or use direct connection (port 5432):
# DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Alternative: Use SUPABASE_DB_URL instead
# SUPABASE_DB_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Google Cloud (if using Google STT instead of OpenAI)
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

## API Endpoints

### Meetings
- `POST /api/meetings/start` - Start a new meeting
- `POST /api/meetings/{id}/stop` - Stop a meeting and generate final summary
- `GET /api/meetings` - Get all meetings (history)
- `GET /api/meetings/{id}` - Get meeting details
- `GET /api/meetings/{id}/summary` - Get meeting summary

### Audio/STT
- `POST /api/audio/stream` - Stream audio for transcription (with speaker diarization)

### Tasks
- `GET /api/meetings/{id}/tasks` - Get extracted tasks
- `POST /api/meetings/{id}/tasks` - Manually add a task

### WebSocket
- `WS /ws/meetings/{id}` - Real-time updates (transcript, summary, tasks)

### Speakers
- `POST /api/speakers/register` - Register a known speaker with voice sample

## Features

### ✅ Implemented
- OpenAI STT with speaker diarization
- LLM-powered meeting summarization (incremental updates)
- LLM-powered task extraction
- WebSocket real-time updates
- Background task processing
- Speaker registration

### 🔄 In Progress
- Audio streaming optimization
- Person detection/identification

## API Documentation

Once running, visit:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

