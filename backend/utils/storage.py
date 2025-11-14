"""
In-memory storage and shared state
"""

# In-memory storage (fallback if DB not available)
meetings_db = {}
audio_streams = {}
tasks_db = {}

# Background task tracking
background_tasks = {}
summary_update_intervals = {}  # meeting_id -> asyncio.Task

