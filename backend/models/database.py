"""
Database Models and Configuration
Supports Supabase (PostgreSQL) or local PostgreSQL
"""

from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory (explicit path)
backend_dir = Path(__file__).parent.parent
env_file = backend_dir / ".env"
load_dotenv(dotenv_path=env_file, override=True)  # override=True ensures env vars are updated

# Database URL - Supabase format:
# postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
# Or direct connection:
# postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("SUPABASE_DB_URL")  # Fallback to Supabase-specific env var
)

# Supabase connection pool settings
# Use NullPool for serverless/connection pooling compatibility
if DATABASE_URL and "supabase" in DATABASE_URL.lower():
    # Supabase works better with connection pooling
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Use NullPool for Supabase connection pooler
        connect_args={
            "sslmode": "require"  # Supabase requires SSL
        }
    )
else:
    # Local PostgreSQL or other
    engine = create_engine(DATABASE_URL, echo=False) if DATABASE_URL else None

# Create session factory (only if engine exists)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Base class for models
Base = declarative_base()


class Meeting(Base):
    """Meeting model"""
    __tablename__ = "meetings"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)  # Meeting title
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active, completed, cancelled
    summary = Column(Text, nullable=True)
    transcript = Column(JSON, default=list)  # List of transcript segments
    tasks = Column(JSON, default=list)  # List of tasks
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """Task model"""
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    meeting_id = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    assignee = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, in_progress, completed
    priority = Column(String, default="medium")  # high, medium, low
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Speaker(Base):
    """Known speaker model"""
    __tablename__ = "speakers"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    audio_reference = Column(Text, nullable=True)  # Path or data URL to voice sample
    created_at = Column(DateTime, default=datetime.utcnow)


class MeetingSpeaker(Base):
    """Junction table linking meetings and speakers (many-to-many)"""
    __tablename__ = "meeting_speakers"
    
    id = Column(String, primary_key=True)
    meeting_id = Column(String, nullable=False, index=True)
    speaker_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    """User settings model"""
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, unique=True, index=True)  # User identifier
    spoken_languages = Column(JSON, default=list)  # Array of language codes (e.g., ["en", "pt", "es"])
    preferred_language = Column(String, nullable=True)  # Preferred language code (e.g., "en")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create tables
def init_db():
    """Initialize database tables"""
    if engine is None:
        raise ValueError("Database URL not configured. Set DATABASE_URL or SUPABASE_DB_URL in .env")
    Base.metadata.create_all(bind=engine)


# Dependency for FastAPI
def get_db():
    """Get database session"""
    if SessionLocal is None:
        raise ValueError("Database not configured. Set DATABASE_URL in .env")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

