"""
Create a meeting with 3 tasks in the database
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from models.database import Meeting, Task, SessionLocal, engine

def create_meeting_with_tasks():
    """Create a meeting and 3 tasks in the database"""
    if engine is None:
        print("❌ Database not configured. Set DATABASE_URL in .env")
        return False
    
    print("🔄 Creating meeting with tasks...")
    
    try:
        db = SessionLocal()
        
        # Create meeting
        meeting_id = str(uuid.uuid4())
        meeting = Meeting(
            id=meeting_id,
            start_time=datetime.utcnow() - timedelta(hours=1),  # Meeting started 1 hour ago
            end_time=datetime.utcnow(),  # Meeting just ended
            status="completed",
            title="Daily Meeting",
            summary="Daily meeting discussing current tasks and blockers.",
            transcript=[],
            tasks=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(meeting)
        db.flush()  # Flush to ensure meeting is saved before creating tasks
        
        print(f"✅ Created meeting: {meeting_id}")
        print(f"   Title: {meeting.title}")
        print(f"   Status: {meeting.status}")
        
        # Define the 3 tasks
        # All tasks due 1 week from now, with different priorities
        due_date = datetime.utcnow() + timedelta(days=7)  # 1 week from now
        
        tasks_data = [
            {
                "title": "Fix bug in login page",
                "description": "Fix bug in login page",
                "assignee": None,  # Only 1 user, so leaving unassigned
                "due_date": due_date,
                "priority": "high",
            },
            {
                "title": "Approve John's PR",
                "description": "Approve John's PR",
                "assignee": None,  # Only 1 user, so leaving unassigned
                "due_date": due_date,
                "priority": "medium",
            },
            {
                "title": "Fix the API bug",
                "description": "Fix the API bug",
                "assignee": None,  # Only 1 user, so leaving unassigned
                "due_date": due_date,
                "priority": "low",
            },
        ]
        
        created_tasks = []
        
        # Create tasks
        for task_data in tasks_data:
            task = Task(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                title=task_data["title"],
                description=task_data["description"],
                assignee=task_data["assignee"],
                due_date=task_data["due_date"],
                status="pending",
                priority=task_data["priority"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(task)
            created_tasks.append(task)
            
            print(f"\n✅ Created task: {task.id}")
            print(f"   Title: {task.title}")
            print(f"   Description: {task.description}")
            print(f"   Assignee: {task.assignee or 'Unassigned'}")
            print(f"   Priority: {task.priority}")
            print(f"   Due Date: {task.due_date}")
            print(f"   Status: {task.status}")
        
        # Update meeting's tasks JSON field with task IDs
        meeting.tasks = [{"task_id": task.id} for task in created_tasks]
        
        db.commit()
        db.close()
        
        print("\n" + "="*60)
        print("✅ Successfully created meeting with 3 tasks!")
        print("="*60)
        print(f"\n📅 Meeting Details:")
        print(f"   ID: {meeting_id}")
        print(f"   Title: {meeting.title}")
        print(f"   Status: {meeting.status}")
        print(f"   Start Time: {meeting.start_time}")
        print(f"   End Time: {meeting.end_time}")
        print(f"\n📋 Tasks Created: {len(created_tasks)}")
        for i, task in enumerate(created_tasks, 1):
            print(f"   {i}. {task.title} ({task.priority} priority)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create meeting with tasks: {e}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

if __name__ == "__main__":
    success = create_meeting_with_tasks()
    sys.exit(0 if success else 1)

