"""
Database helper functions for reading and writing meeting data
"""

from datetime import datetime
from typing import Optional, Dict, List

# Import database models
try:
    from models.database import Meeting, SessionLocal
    DB_AVAILABLE = True
except Exception as e:
    print(f"Database not available: {e}")
    DB_AVAILABLE = False
    SessionLocal = None

# Import storage for fallback
from utils.storage import meetings_db


def get_meeting_from_db_or_memory(meeting_id: str) -> Optional[Dict]:
    """Get meeting from database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                result = {
                    "meeting_id": meeting.id,
                    "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                    "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                    "status": meeting.status,
                    "transcript": meeting.transcript or [],
                    "summary": meeting.summary,
                    "tasks": meeting.tasks or [],
                }
                db.close()
                return result
            db.close()
        except Exception as e:
            print(f"Error reading from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Fallback to in-memory
    return meetings_db.get(meeting_id)


def save_meeting_to_db(meeting_data: dict):
    """Save meeting to database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meeting = db.query(Meeting).filter(Meeting.id == meeting_data["meeting_id"]).first()
            
            if meeting:
                # Update existing
                meeting.start_time = datetime.fromisoformat(meeting_data["start_time"]) if meeting_data.get("start_time") else meeting.start_time
                meeting.end_time = datetime.fromisoformat(meeting_data["end_time"]) if meeting_data.get("end_time") else meeting.end_time
                meeting.status = meeting_data.get("status", meeting.status)
                meeting.transcript = meeting_data.get("transcript", meeting.transcript)
                meeting.summary = meeting_data.get("summary", meeting.summary)
                meeting.tasks = meeting_data.get("tasks", meeting.tasks)
                meeting.updated_at = datetime.utcnow()
            else:
                # Create new
                meeting = Meeting(
                    id=meeting_data["meeting_id"],
                    start_time=datetime.fromisoformat(meeting_data["start_time"]) if meeting_data.get("start_time") else datetime.utcnow(),
                    end_time=datetime.fromisoformat(meeting_data["end_time"]) if meeting_data.get("end_time") else None,
                    status=meeting_data.get("status", "active"),
                    transcript=meeting_data.get("transcript", []),
                    summary=meeting_data.get("summary"),
                    tasks=meeting_data.get("tasks", []),
                )
                db.add(meeting)
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error saving to database: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    # Always update in-memory as well (for background tasks and fallback)
    meetings_db[meeting_data["meeting_id"]] = meeting_data


def get_all_meetings_from_db() -> List[Dict]:
    """Get all meetings from database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meetings = db.query(Meeting).all()
            result = []
            for meeting in meetings:
                result.append({
                    "meeting_id": meeting.id,
                    "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                    "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                    "status": meeting.status,
                    "transcript": meeting.transcript or [],
                    "summary": meeting.summary,
                    "tasks": meeting.tasks or [],
                })
            db.close()
            return result
        except Exception as e:
            print(f"Error reading meetings from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Fallback to in-memory
    return list(meetings_db.values())

