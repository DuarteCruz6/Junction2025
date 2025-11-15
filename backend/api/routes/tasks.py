"""
Task management endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid

from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db, get_all_meetings_from_db
from models.database import Task, SessionLocal

router = APIRouter()


@router.get("/api/meetings/{meeting_id}/tasks")
async def get_meeting_tasks(meeting_id: str):
    """Get extracted tasks from a meeting"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    tasks = meeting.get("tasks", [])
    
    return JSONResponse(content={"tasks": tasks})


@router.post("/api/meetings/{meeting_id}/tasks")
async def add_task(meeting_id: str, task: dict):
    """Manually add a task to a meeting"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    task_id = str(uuid.uuid4())
    title = task.get("title", "Untitled Task")
    description = task.get("description", "")
    assignee = task.get("assignee")
    due_date_str = task.get("due_date")
    priority = task.get("priority", "medium")
    
    # Parse due_date if provided
    due_date = None
    if due_date_str:
        try:
            from dateutil import parser
            due_date = parser.parse(due_date_str)
        except Exception:
            pass
    
    # Save to Task table
    if SessionLocal:
        try:
            db = SessionLocal()
            db_task = Task(
                id=task_id,
                meeting_id=meeting_id,
                title=title,
                description=description,
                assignee=assignee,
                due_date=due_date,
                is_concluded=False,
                priority=priority,
            )
            db.add(db_task)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[Tasks API] ❌ Error saving task to database: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    task_data = {
        "task_id": task_id,
        "title": title,
        "description": description,
        "assignee": assignee,
        "due_date": due_date_str,
        "is_concluded": False,
        "priority": priority,
        "created_at": datetime.now().isoformat(),
    }
    
    meeting["tasks"].append(task_data)
    
    # Save to database
    save_meeting_to_db(meeting)
    
    # Broadcast task update
    await websocket_manager.send_tasks_update(
        meeting_id=meeting_id,
        tasks=meeting["tasks"]
    )
    
    return JSONResponse(content=task_data)


@router.get("/api/tasks/incomplete")
async def get_incomplete_tasks():
    """Get all tasks that are not completed/concluded"""
    try:
        if SessionLocal:
            db = SessionLocal()
            # Get all tasks where is_concluded is False
            tasks = db.query(Task).filter(Task.is_concluded == False).all()
            result = []
            for task in tasks:
                result.append({
                    "task_id": task.id,
                    "meeting_id": task.meeting_id,
                    "title": task.title,
                    "description": task.description,
                    "assignee": task.assignee,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "is_concluded": task.is_concluded,
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                })
            db.close()
            return JSONResponse(content={"tasks": result})
        else:
            # Fallback: get from meetings
            meetings = get_all_meetings_from_db()
            all_tasks = []
            for meeting in meetings:
                tasks = meeting.get("tasks", [])
                for task in tasks:
                    if not task.get("is_concluded", False):
                        all_tasks.append(task)
            return JSONResponse(content={"tasks": all_tasks})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get incomplete tasks: {str(e)}")


@router.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: dict):
    """Update task is_concluded status (e.g., mark as completed)"""
    # Support both old "status" field and new "is_concluded" field for backward compatibility
    is_concluded = status.get("is_concluded")
    if is_concluded is None:
        # Try to convert old "status" field to is_concluded
        old_status = status.get("status")
        if old_status:
            is_concluded = old_status.lower() in ["completed", "done", "finished"]
        else:
            raise HTTPException(status_code=400, detail="is_concluded or status is required")
    
    try:
        if SessionLocal:
            db = SessionLocal()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.is_concluded = bool(is_concluded)
                task.updated_at = datetime.utcnow()
                db.commit()
                db.close()
                
                # Also update in meeting's tasks array
                meeting = get_meeting_from_db_or_memory(task.meeting_id)
                if meeting:
                    for t in meeting.get("tasks", []):
                        if t.get("task_id") == task_id:
                            t["is_concluded"] = bool(is_concluded)
                    save_meeting_to_db(meeting)
                
                return JSONResponse(content={"task_id": task_id, "is_concluded": bool(is_concluded)})
            else:
                db.close()
                raise HTTPException(status_code=404, detail="Task not found")
        else:
            # Fallback: update in meetings
            meetings = get_all_meetings_from_db()
            for meeting in meetings:
                tasks = meeting.get("tasks", [])
                for task in tasks:
                    if task.get("task_id") == task_id:
                        task["is_concluded"] = bool(is_concluded)
                        save_meeting_to_db(meeting)
                        return JSONResponse(content={"task_id": task_id, "is_concluded": bool(is_concluded)})
            raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")

