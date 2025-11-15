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
    task_data = {
        "task_id": task_id,
        "description": task.get("description", ""),
        "assignee": task.get("assignee"),
        "due_date": task.get("due_date"),
        "status": "pending",
        "priority": task.get("priority", "medium"),
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
            # Get all tasks where status is not 'completed'
            tasks = db.query(Task).filter(Task.status != "completed").all()
            result = []
            for task in tasks:
                result.append({
                    "task_id": task.id,
                    "meeting_id": task.meeting_id,
                    "description": task.description,
                    "assignee": task.assignee,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "status": task.status,
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
                    if task.get("status") != "completed":
                        all_tasks.append(task)
            return JSONResponse(content={"tasks": all_tasks})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get incomplete tasks: {str(e)}")


@router.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: dict):
    """Update task status (e.g., mark as completed)"""
    new_status = status.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    try:
        if SessionLocal:
            db = SessionLocal()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = new_status
                task.updated_at = datetime.utcnow()
                db.commit()
                db.close()
                
                # Also update in meeting's tasks array
                meeting = get_meeting_from_db_or_memory(task.meeting_id)
                if meeting:
                    for t in meeting.get("tasks", []):
                        if t.get("task_id") == task_id:
                            t["status"] = new_status
                    save_meeting_to_db(meeting)
                
                return JSONResponse(content={"task_id": task_id, "status": new_status})
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
                        task["status"] = new_status
                        save_meeting_to_db(meeting)
                        return JSONResponse(content={"task_id": task_id, "status": new_status})
            raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")

