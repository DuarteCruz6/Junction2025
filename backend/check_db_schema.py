"""
Database Schema Checker
Checks the current database schema to see what needs to be migrated
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, text
from models.database import engine, SessionLocal

def check_database_schema():
    """Check current database schema"""
    if engine is None:
        print("❌ Database not configured. Set DATABASE_URL in .env")
        return False
    
    print("🔍 Checking database schema...")
    print("=" * 60)
    
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📊 Found {len(tables)} tables: {', '.join(tables)}")
        
        # Check meetings table
        print("\n" + "=" * 60)
        print("📋 MEETINGS TABLE")
        print("=" * 60)
        if 'meetings' in tables:
            columns = inspector.get_columns('meetings')
            column_names = [col['name'] for col in columns]
            print(f"Columns: {', '.join(column_names)}")
            
            has_title = 'title' in column_names
            if has_title:
                print("\n⚠️  'title' column exists (should be removed)")
                print("   ⚠️  Migration needed: Remove 'title' column")
            else:
                print("\n✅ 'title' column doesn't exist (correct)")
        else:
            print("⚠️  'meetings' table doesn't exist")
        
        # Check tasks table
        print("\n" + "=" * 60)
        print("📋 TASKS TABLE")
        print("=" * 60)
        if 'tasks' in tables:
            columns = inspector.get_columns('tasks')
            column_names = [col['name'] for col in columns]
            print(f"Columns: {', '.join(column_names)}")
            
            has_title = 'title' in column_names
            print(f"\n✅ 'title' column: {'EXISTS' if has_title else 'MISSING'}")
            
            if not has_title:
                print("   ⚠️  Migration needed: Add 'title' column")
        else:
            print("⚠️  'tasks' table doesn't exist")
        
        # Check meeting_speakers table
        print("\n" + "=" * 60)
        print("📋 MEETING_SPEAKERS TABLE")
        print("=" * 60)
        if 'meeting_speakers' in tables:
            columns = inspector.get_columns('meeting_speakers')
            column_names = [col['name'] for col in columns]
            print(f"Columns: {', '.join(column_names)}")
            print("\n⚠️  Migration needed: Drop 'meeting_speakers' table")
        else:
            print("✅ 'meeting_speakers' table doesn't exist (correct)")
        
        # Check other tables
        print("\n" + "=" * 60)
        print("📋 OTHER TABLES")
        print("=" * 60)
        expected_tables = ['speakers', 'user_settings']
        for table_name in expected_tables:
            if table_name in tables:
                print(f"✅ {table_name}: EXISTS")
            else:
                print(f"⚠️  {table_name}: MISSING")
        
        print("\n" + "=" * 60)
        print("📝 SUMMARY")
        print("=" * 60)
        
        needs_migration = False
        if 'meetings' in tables:
            columns = [col['name'] for col in inspector.get_columns('meetings')]
            if 'title' in columns:
                print("❌ 'meetings' table has 'title' column (should be removed)")
                needs_migration = True
        
        if 'tasks' in tables:
            columns = [col['name'] for col in inspector.get_columns('tasks')]
            if 'title' not in columns:
                print("❌ 'tasks' table is missing 'title' column")
                needs_migration = True
        
        if 'meeting_speakers' in tables:
            print("❌ 'meeting_speakers' table still exists (should be removed)")
            needs_migration = True
        
        if not needs_migration:
            print("✅ Database schema is up to date!")
        else:
            print("\n⚠️  Database needs migration. Run: python migrate_db.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error checking schema: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_database_schema()

