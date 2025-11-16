"""
User settings management endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from models.database import get_db, UserSettings
from sqlalchemy.orm import Session

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Settings update model"""
    spoken_languages: Optional[List[str]] = None
    preferred_language: Optional[str] = None
    subtitles_enabled: Optional[bool] = None
    font_size: Optional[str] = None  # "small", "medium", "large", "xlarge"
    screen_reader_enabled: Optional[bool] = None


class SettingsResponse(BaseModel):
    """Settings response model"""
    id: str
    user_id: str
    spoken_languages: List[str]
    preferred_language: Optional[str]
    subtitles_enabled: bool
    font_size: str
    screen_reader_enabled: bool
    created_at: datetime
    updated_at: datetime


@router.get("/api/settings/{user_id}")
async def get_settings(user_id: str, db: Session = Depends(get_db)):
    """Get user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    if not settings:
        # Return default settings if not found
        return JSONResponse(content={
            "id": None,
            "user_id": user_id,
            "spoken_languages": [],
            "preferred_language": None,
            "subtitles_enabled": True,
            "font_size": "medium",
            "screen_reader_enabled": False,
            "created_at": None,
            "updated_at": None,
        })
    
    return JSONResponse(content={
        "id": settings.id,
        "user_id": settings.user_id,
        "spoken_languages": settings.spoken_languages or [],
        "preferred_language": settings.preferred_language,
        "subtitles_enabled": settings.subtitles_enabled if settings.subtitles_enabled is not None else True,
        "font_size": settings.font_size if settings.font_size else "medium",
        "screen_reader_enabled": settings.screen_reader_enabled if settings.screen_reader_enabled is not None else False,
        "created_at": settings.created_at.isoformat() if settings.created_at else None,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    })


@router.put("/api/settings/{user_id}")
async def update_settings(
    user_id: str,
    settings_update: SettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update user settings (creates if doesn't exist)"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    if not settings:
        # Create new settings
        settings = UserSettings(
            id=str(uuid.uuid4()),
            user_id=user_id,
            spoken_languages=settings_update.spoken_languages or [],
            preferred_language=settings_update.preferred_language,
            subtitles_enabled=settings_update.subtitles_enabled if settings_update.subtitles_enabled is not None else True,
            font_size=settings_update.font_size if settings_update.font_size else "medium",
            screen_reader_enabled=settings_update.screen_reader_enabled if settings_update.screen_reader_enabled is not None else False,
        )
        db.add(settings)
    else:
        # Update existing settings
        if settings_update.spoken_languages is not None:
            settings.spoken_languages = settings_update.spoken_languages
        if settings_update.preferred_language is not None:
            settings.preferred_language = settings_update.preferred_language
        if settings_update.subtitles_enabled is not None:
            settings.subtitles_enabled = settings_update.subtitles_enabled
        if settings_update.font_size is not None:
            settings.font_size = settings_update.font_size
        if settings_update.screen_reader_enabled is not None:
            settings.screen_reader_enabled = settings_update.screen_reader_enabled
        settings.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(settings)
        
        return JSONResponse(content={
            "id": settings.id,
            "user_id": settings.user_id,
            "spoken_languages": settings.spoken_languages or [],
            "preferred_language": settings.preferred_language,
            "subtitles_enabled": settings.subtitles_enabled if settings.subtitles_enabled is not None else True,
            "font_size": settings.font_size if settings.font_size else "medium",
            "screen_reader_enabled": settings.screen_reader_enabled if settings.screen_reader_enabled is not None else False,
            "created_at": settings.created_at.isoformat() if settings.created_at else None,
            "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
        })
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.patch("/api/settings/{user_id}")
async def patch_settings(
    user_id: str,
    settings_update: SettingsUpdate,
    db: Session = Depends(get_db)
):
    """Partially update user settings (same as PUT for now)"""
    return await update_settings(user_id, settings_update, db)

