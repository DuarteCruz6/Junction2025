"""
Task management endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid

from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db

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

