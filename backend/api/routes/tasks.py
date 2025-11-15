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
    """Get extracted tasks from a meeting (from both JSON field and tasks table)"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get tasks from meeting's JSON field
    json_tasks = meeting.get("tasks", [])
    
    # Also get tasks from the tasks table
    db_tasks = []
    if SessionLocal:
        try:
            db = SessionLocal()
            tasks_from_db = db.query(Task).filter(Task.meeting_id == meeting_id).all()
            for task in tasks_from_db:
                db_tasks.append({
                    "task_id": task.id,
                    "id": task.id,
                    "meeting_id": task.meeting_id,
                    "title": task.title,
                    "description": task.description,
                    "assignee": task.assignee,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "status": task.status,
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                })
            db.close()
        except Exception as e:
            print(f"Error getting tasks from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Merge tasks, prioritizing database tasks (they have IDs)
    # Create a map of task_ids from JSON tasks to avoid duplicates
    json_task_ids = {task.get("task_id") or task.get("id") for task in json_tasks if task.get("task_id") or task.get("id")}
    
    # Add JSON tasks that aren't in the database
    for json_task in json_tasks:
        task_id = json_task.get("task_id") or json_task.get("id")
        if task_id and task_id not in {t["task_id"] for t in db_tasks}:
            db_tasks.append(json_task)
    
    return JSONResponse(content={"tasks": db_tasks})


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
                    "title": task.title,
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


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a single task by ID with meeting information"""
    try:
        if SessionLocal:
            db = SessionLocal()
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                db.close()
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Get meeting information
            meeting = get_meeting_from_db_or_memory(task.meeting_id)
            meeting_info = None
            if meeting:
                meeting_info = {
                    "id": meeting.get("id"),
                    "title": meeting.get("title"),
                    "start_time": meeting.get("start_time"),
                    "status": meeting.get("status"),
                }
            
            task_data = {
                "task_id": task.id,
                "meeting_id": task.meeting_id,
                "title": task.title,
                "description": task.description,
                "assignee": task.assignee,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "status": task.status,
                "priority": task.priority,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "meeting": meeting_info,
            }
            db.close()
            return JSONResponse(content=task_data)
        else:
            # Fallback: get from meetings
            meetings = get_all_meetings_from_db()
            for meeting in meetings:
                tasks = meeting.get("tasks", [])
                for task in tasks:
                    if task.get("task_id") == task_id or task.get("id") == task_id:
                        meeting_info = {
                            "id": meeting.get("id"),
                            "title": meeting.get("title"),
                            "start_time": meeting.get("start_time"),
                            "status": meeting.get("status"),
                        }
                        task_data = task.copy()
                        task_data["meeting"] = meeting_info
                        return JSONResponse(content=task_data)
            raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


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

