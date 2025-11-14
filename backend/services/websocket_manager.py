"""
WebSocket Manager
Handles real-time WebSocket connections for live updates
"""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import asyncio

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # meeting_id -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, meeting_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = set()
        
        self.active_connections[meeting_id].add(websocket)
        print(f"WebSocket connected for meeting {meeting_id}. Total connections: {len(self.active_connections[meeting_id])}")
    
    def disconnect(self, websocket: WebSocket, meeting_id: str):
        """Remove a WebSocket connection"""
        if meeting_id in self.active_connections:
            self.active_connections[meeting_id].discard(websocket)
            if len(self.active_connections[meeting_id]) == 0:
                del self.active_connections[meeting_id]
            print(f"WebSocket disconnected for meeting {meeting_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
    
    async def broadcast_to_meeting(self, meeting_id: str, message: dict):
        """Broadcast message to all connections for a meeting"""
        if meeting_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[meeting_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to meeting {meeting_id}: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.active_connections[meeting_id].discard(conn)
    
    async def send_transcript_update(self, meeting_id: str, transcript_entry: dict):
        """Send transcript update to meeting participants"""
        message = {
            "type": "transcript_update",
            "data": transcript_entry
        }
        await self.broadcast_to_meeting(meeting_id, message)
    
    async def send_summary_update(self, meeting_id: str, summary: str):
        """Send summary update to meeting participants"""
        message = {
            "type": "summary_update",
            "data": {
                "summary": summary,
                "timestamp": str(datetime.utcnow())
            }
        }
        await self.broadcast_to_meeting(meeting_id, message)
    
    async def send_tasks_update(self, meeting_id: str, tasks: list):
        """Send tasks update to meeting participants"""
        message = {
            "type": "tasks_update",
            "data": {
                "tasks": tasks,
                "timestamp": str(datetime.utcnow())
            }
        }
        await self.broadcast_to_meeting(meeting_id, message)
    
    async def send_status_update(self, meeting_id: str, status: str, message: str = None):
        """Send status update to meeting participants"""
        update_message = {
            "type": "status_update",
            "data": {
                "status": status,
                "message": message,
                "timestamp": str(datetime.utcnow())
            }
        }
        await self.broadcast_to_meeting(meeting_id, update_message)


# Singleton instance
websocket_manager = WebSocketManager()

