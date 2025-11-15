"""
Create a test task in the database for UI testing
"""

import sys
from pathlib import Path
from datetime import datetime
import uuid

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from models.database import Task, SessionLocal, engine
from utils.db_helpers import get_all_meetings_from_db

def create_test_task():
    """Create a test task in the database"""
    if engine is None:
        print("❌ Database not configured. Set DATABASE_URL in .env")
        return False
    
    print("🔄 Creating test task...")
    
    try:
        # Get an existing meeting or create a fake meeting_id
        meetings = get_all_meetings_from_db()
        meeting_id = None
        
        if meetings and len(meetings) > 0:
            meeting_id = meetings[0].get("meeting_id") or meetings[0].get("id")
            print(f"📅 Using existing meeting: {meeting_id}")
        else:
            # Create a fake meeting_id for testing
            meeting_id = str(uuid.uuid4())
            print(f"📅 Using fake meeting_id: {meeting_id}")
        
        db = SessionLocal()
        
        # Create test task
        test_task = Task(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            title="Review project proposal",
            description="Review the Q4 project proposal document and provide feedback by end of week. Focus on budget allocation and timeline feasibility.",
            assignee="John Doe",
            due_date=datetime(2025, 2, 15),
            status="pending",
            priority="high",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(test_task)
        db.commit()
        
        print("\n✅ Test task created successfully!")
        print(f"\n📋 Task Details:")
        print(f"   ID: {test_task.id}")
        print(f"   Title: {test_task.title}")
        print(f"   Description: {test_task.description}")
        print(f"   Meeting ID: {test_task.meeting_id}")
        print(f"   Assignee: {test_task.assignee}")
        print(f"   Status: {test_task.status}")
        print(f"   Priority: {test_task.priority}")
        print(f"   Due Date: {test_task.due_date}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create test task: {e}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

if __name__ == "__main__":
    success = create_test_task()
    sys.exit(0 if success else 1)

