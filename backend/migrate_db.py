"""
Database Migration Script
Updates the database schema to match the current models:
1. Adds 'title' column to 'meetings' table if it doesn't exist
2. Adds 'title' column to 'tasks' table if it doesn't exist
3. Drops 'meeting_speakers' table if it exists
4. Adds 'subtitles_enabled' column to 'user_settings' table if it doesn't exist
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from models.database import engine, SessionLocal, Base

def migrate_database():
    """Apply database migrations"""
    if engine is None:
        print("❌ Database not configured. Set DATABASE_URL in .env")
        return False
    
    print("🔄 Starting database migration...")
    
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            
            # 1. Add 'title' column to 'meetings' table if it doesn't exist
            print("\n1. Checking 'meetings' table...")
            if 'meetings' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('meetings')]
                if 'title' not in columns:
                    print("   ➕ Adding 'title' column to 'meetings' table...")
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN title VARCHAR"))
                    conn.commit()
                    print("   ✅ 'title' column added successfully")
                else:
                    print("   ✅ 'title' column already exists")
            else:
                print("   ⚠️  'meetings' table doesn't exist (will be created on next startup)")
            
            # 2. Add 'title' column to 'tasks' table if it doesn't exist
            print("\n2. Checking 'tasks' table...")
            if 'tasks' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('tasks')]
                if 'title' not in columns:
                    print("   ➕ Adding 'title' column to 'tasks' table...")
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN title VARCHAR"))
                    conn.commit()
                    print("   ✅ 'title' column added successfully")
                else:
                    print("   ✅ 'title' column already exists")
            else:
                print("   ⚠️  'tasks' table doesn't exist (will be created on next startup)")
            
            # 3. Drop 'meeting_speakers' table if it exists
            print("\n3. Checking 'meeting_speakers' table...")
            if 'meeting_speakers' in inspector.get_table_names():
                print("   🗑️  Dropping 'meeting_speakers' table...")
                conn.execute(text("DROP TABLE IF EXISTS meeting_speakers CASCADE"))
                conn.commit()
                print("   ✅ 'meeting_speakers' table dropped successfully")
            else:
                print("   ✅ 'meeting_speakers' table doesn't exist (nothing to drop)")
            
            # 4. Add 'subtitles_enabled' column to 'user_settings' table if it doesn't exist
            print("\n4. Checking 'user_settings' table...")
            if 'user_settings' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('user_settings')]
                if 'subtitles_enabled' not in columns:
                    print("   ➕ Adding 'subtitles_enabled' column to 'user_settings' table...")
                    conn.execute(text("ALTER TABLE user_settings ADD COLUMN subtitles_enabled BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("   ✅ 'subtitles_enabled' column added successfully")
                else:
                    print("   ✅ 'subtitles_enabled' column already exists")
                
                # Add 'font_size' column if it doesn't exist
                if 'font_size' not in columns:
                    print("   ➕ Adding 'font_size' column to 'user_settings' table...")
                    conn.execute(text("ALTER TABLE user_settings ADD COLUMN font_size VARCHAR DEFAULT 'medium'"))
                    conn.commit()
                    print("   ✅ 'font_size' column added successfully")
                else:
                    print("   ✅ 'font_size' column already exists")
                
                # Add 'screen_reader_enabled' column if it doesn't exist
                if 'screen_reader_enabled' not in columns:
                    print("   ➕ Adding 'screen_reader_enabled' column to 'user_settings' table...")
                    conn.execute(text("ALTER TABLE user_settings ADD COLUMN screen_reader_enabled BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("   ✅ 'screen_reader_enabled' column added successfully")
                else:
                    print("   ✅ 'screen_reader_enabled' column already exists")
            else:
                print("   ⚠️  'user_settings' table doesn't exist (will be created on next startup)")
            
            # 5. Check if 'reminders' table exists, create if not
            print("\n5. Checking 'reminders' table...")
            if 'reminders' not in inspector.get_table_names():
                print("   ➕ Creating 'reminders' table...")
                Base.metadata.create_all(bind=engine)
                print("   ✅ 'reminders' table created successfully")
            else:
                print("   ✅ 'reminders' table already exists")
            
            # 6. Ensure all other tables are up to date
            print("\n6. Ensuring all tables are up to date...")
            Base.metadata.create_all(bind=engine)
            print("   ✅ All tables are up to date")
            
        print("\n✅ Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)

