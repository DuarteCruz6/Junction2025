"""
Reminder management endpoints for elderly care
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid
from typing import Optional

from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db
from models.database import Reminder, SessionLocal

router = APIRouter()


@router.get("/api/meetings/{meeting_id}/reminders")
async def get_meeting_reminders(meeting_id: str):
    """Get extracted reminders from a family call"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get reminders from the reminders table
    db_reminders = []
    if SessionLocal:
        try:
            db = SessionLocal()
            reminders_from_db = db.query(Reminder).filter(Reminder.meeting_id == meeting_id).all()
            for reminder in reminders_from_db:
                db_reminders.append({
                    "reminder_id": reminder.id,
                    "id": reminder.id,
                    "meeting_id": reminder.meeting_id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "reminder_date": reminder.reminder_date.isoformat() if reminder.reminder_date else None,
                    "reminder_time": reminder.reminder_time,
                    "is_recurring": reminder.is_recurring,
                    "recurrence_pattern": reminder.recurrence_pattern,
                    "status": reminder.status,
                    "priority": reminder.priority,
                    "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
                })
            db.close()
        except Exception as e:
            print(f"Error getting reminders from database: {e}")
            if 'db' in locals():
                db.close()
    
    return JSONResponse(content={"reminders": db_reminders})


@router.post("/api/meetings/{meeting_id}/reminders")
async def add_reminder(meeting_id: str, reminder: dict):
    """Manually add a reminder to a call"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Call not found")
    
    reminder_id = str(uuid.uuid4())
    
    # Parse reminder_date if provided as string
    reminder_date = None
    if reminder.get("reminder_date"):
        try:
            if isinstance(reminder["reminder_date"], str):
                reminder_date = datetime.fromisoformat(reminder["reminder_date"].replace("Z", "+00:00"))
            else:
                reminder_date = reminder["reminder_date"]
        except Exception as e:
            print(f"Error parsing reminder_date: {e}")
    
    reminder_data = {
        "reminder_id": reminder_id,
        "title": reminder.get("title"),
        "description": reminder.get("description", ""),
        "reminder_date": reminder_date,
        "reminder_time": reminder.get("reminder_time"),
        "is_recurring": reminder.get("is_recurring", False),
        "recurrence_pattern": reminder.get("recurrence_pattern"),
        "status": "active",
        "priority": reminder.get("priority", "medium"),
        "created_at": datetime.now().isoformat(),
    }
    
    # Save to database
    if SessionLocal:
        try:
            db = SessionLocal()
            db_reminder = Reminder(
                id=reminder_id,
                meeting_id=meeting_id,
                title=reminder_data["title"],
                description=reminder_data["description"],
                reminder_date=reminder_date,
                reminder_time=reminder_data["reminder_time"],
                is_recurring=reminder_data["is_recurring"],
                recurrence_pattern=reminder_data["recurrence_pattern"],
                status="active",
                priority=reminder_data["priority"],
            )
            db.add(db_reminder)
            db.commit()
            db.refresh(db_reminder)
            db.close()
        except Exception as e:
            print(f"Error saving reminder to database: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    # Broadcast reminder update
    await websocket_manager.send_reminders_update(
        meeting_id=meeting_id,
        reminders=[reminder_data]
    )
    
    return JSONResponse(content=reminder_data)


@router.get("/api/reminders/active")
async def get_active_reminders():
    """Get all active reminders across all calls"""
    db_reminders = []
    if SessionLocal:
        try:
            db = SessionLocal()
            reminders_from_db = db.query(Reminder).filter(Reminder.status == "active").order_by(Reminder.reminder_date.asc()).all()
            for reminder in reminders_from_db:
                db_reminders.append({
                    "reminder_id": reminder.id,
                    "id": reminder.id,
                    "meeting_id": reminder.meeting_id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "reminder_date": reminder.reminder_date.isoformat() if reminder.reminder_date else None,
                    "reminder_time": reminder.reminder_time,
                    "is_recurring": reminder.is_recurring,
                    "recurrence_pattern": reminder.recurrence_pattern,
                    "status": reminder.status,
                    "priority": reminder.priority,
                    "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
                })
            db.close()
        except Exception as e:
            print(f"Error getting active reminders from database: {e}")
            if 'db' in locals():
                db.close()
    
    return JSONResponse(content={"reminders": db_reminders})


@router.patch("/api/reminders/{reminder_id}")
async def update_reminder(reminder_id: str, reminder_update: dict):
    """Update a reminder (e.g., mark as completed)"""
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        db = SessionLocal()
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        
        if not reminder:
            db.close()
            raise HTTPException(status_code=404, detail="Reminder not found")
        
        # Update fields
        if "status" in reminder_update:
            reminder.status = reminder_update["status"]
        if "title" in reminder_update:
            reminder.title = reminder_update["title"]
        if "description" in reminder_update:
            reminder.description = reminder_update["description"]
        if "priority" in reminder_update:
            reminder.priority = reminder_update["priority"]
        
        reminder.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(reminder)
        db.close()
        
        return JSONResponse(content={
            "reminder_id": reminder.id,
            "id": reminder.id,
            "meeting_id": reminder.meeting_id,
            "title": reminder.title,
            "description": reminder.description,
            "reminder_date": reminder.reminder_date.isoformat() if reminder.reminder_date else None,
            "reminder_time": reminder.reminder_time,
            "is_recurring": reminder.is_recurring,
            "recurrence_pattern": reminder.recurrence_pattern,
            "status": reminder.status,
            "priority": reminder.priority,
            "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
        })
    except HTTPException:
        raise
    except Exception as e:
        if 'db' in locals():
            db.rollback()
            db.close()
        raise HTTPException(status_code=500, detail=f"Failed to update reminder: {str(e)}")

