"""
Background processing tasks for meetings
"""

import asyncio
import uuid
from datetime import datetime

from services.llm_service import llm_service
from services.websocket_manager import websocket_manager
from utils.storage import meetings_db
from utils.db_helpers import save_meeting_to_db


async def process_summary_update(meeting_id: str):
    """Background task to periodically update meeting summary"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            
            # Only update if we have new transcript segments (at least 3)
            if len(transcript) >= 3:
                previous_summary = meeting.get("summary")
                
                # Generate summary using LLM
                result = await llm_service.summarize_meeting(
                    transcript=transcript,
                    previous_summary=previous_summary,
                    incremental=True
                )
                
                if result["success"]:
                    meeting["summary"] = result["summary"]
                    
                    # Save to database
                    save_meeting_to_db(meeting)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_summary_update(
                        meeting_id=meeting_id,
                        summary=result["summary"]
                    )
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in summary update task for {meeting_id}: {e}")
            await asyncio.sleep(30)


async def process_task_extraction(meeting_id: str):
    """Background task to periodically extract tasks"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            existing_tasks = meeting.get("tasks", [])
            
            # Only extract if we have transcript segments
            if len(transcript) >= 5:  # Need some content to extract tasks
                result = await llm_service.extract_tasks(
                    transcript=transcript,
                    existing_tasks=existing_tasks
                )
                
                if result["success"] and result["tasks"]:
                    # Add new tasks
                    for task in result["tasks"]:
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
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_tasks_update(
                        meeting_id=meeting_id,
                        tasks=meeting["tasks"]
                    )
            
            # Wait 60 seconds before next extraction
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Error in task extraction task for {meeting_id}: {e}")
            await asyncio.sleep(60)

