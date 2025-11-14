# Quick Setup Guide

## Prerequisites

1. **Python 3.11+** installed
2. **OpenAI API Key** - Get one from https://platform.openai.com/api-keys
3. (Recommended) **Supabase Account** - For database storage (used by Spectacles)
   - Sign up at https://supabase.com
   - Create a new project
   - Get your database connection string from Settings > Database

## Installation

### 1. Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `backend/` directory:

```env
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Recommended: Supabase Database
# Get from Supabase Dashboard > Settings > Database > Connection string
# Use "Connection Pooling" mode (port 6543) for better performance
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Or use direct connection:
# DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

**Getting Supabase Connection String:**
1. Go to your Supabase project dashboard
2. Click **Settings** → **Database**
3. Scroll to **Connection string**
4. Select **Connection pooling** mode (recommended)
5. Copy the connection string and replace `[YOUR-PASSWORD]` with your database password

### 3. Run the Server

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## Testing the Integration

### 1. Start a Meeting

```bash
curl -X POST http://localhost:8000/api/meetings/start
```

Response:
```json
{
  "meeting_id": "uuid-here",
  "status": "started",
  "start_time": "2025-01-XX..."
}
```

### 2. Send Audio for Transcription

```bash
curl -X POST http://localhost:8000/api/audio/stream \
  -H "X-Meeting-ID: your-meeting-id" \
  -F "file=@path/to/audio.m4a"
```

### 3. Get Meeting Summary

```bash
curl http://localhost:8000/api/meetings/{meeting-id}/summary
```

### 4. Get Extracted Tasks

```bash
curl http://localhost:8000/api/meetings/{meeting-id}/tasks
```

## WebSocket Testing

You can test WebSocket connections using a tool like `websocat` or a browser console:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/meetings/{meeting-id}');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

## Register Known Speakers

To improve speaker diarization, register known speakers:

```bash
curl -X POST http://localhost:8000/api/speakers/register \
  -F "name=John Doe" \
  -F "audio_file=@path/to/john_voice_sample.m4a"
```

## API Documentation

Once the server is running:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Troubleshooting

### OpenAI API Key Error
- Make sure your `.env` file has `OPENAI_API_KEY` set
- Verify the key is valid at https://platform.openai.com/api-keys

### Import Errors
- Make sure you've activated the virtual environment
- Run `pip install -r requirements.txt` again

### Port Already in Use
- Change the port in `main.py` or use: `uvicorn main:app --port 8001`

