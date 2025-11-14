"""
WebSocket endpoints for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory

router = APIRouter()


@router.websocket("/ws/meetings/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket, meeting_id)
    
    try:
        # Send initial state
        meeting = get_meeting_from_db_or_memory(meeting_id)
        if meeting:
            await websocket_manager.send_personal_message({
                "type": "initial_state",
                "data": {
                    "meeting_id": meeting_id,
                    "status": meeting["status"],
                    "summary": meeting.get("summary"),
                    "tasks": meeting.get("tasks", []),
                    "transcript_count": len(meeting.get("transcript", [])),
                }
            }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming messages if needed
                # For now, just keep connection alive
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        print(f"WebSocket error for meeting {meeting_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, meeting_id)

