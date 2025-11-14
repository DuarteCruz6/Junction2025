# Backend

This folder contains the Python FastAPI backend application that serves as the API layer connecting the web app and mobile app.

## Purpose

The backend handles:
- API endpoints for web and mobile applications
- ML model integrations (LLMs, speech recognition, facial recognition, etc.)
- Business logic and data processing
- Communication between frontend applications

## Structure

```
backend/
├── main.py              # FastAPI application entry point
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration for containerization
├── docker-compose.yml   # Docker Compose configuration
└── .dockerignore        # Files to exclude from Docker builds
```

## Technology Stack

- **Framework:** FastAPI
- **Language:** Python 3.11+
- **Server:** Uvicorn
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

Create a `.env` file in this directory:
```
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8081
```

## Future Development

- ML model endpoints (speech-to-text, facial recognition, etc.)
- LLM integrations
- Database integration
- Authentication and authorization
- Audio/video processing endpoints

