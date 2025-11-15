"""
Database helper functions for reading and writing meeting data
"""

from datetime import datetime
from typing import Optional, Dict, List

# Import database models
try:
    from models.database import Meeting, Speaker, SessionLocal
    import uuid
    DB_AVAILABLE = True
except Exception as e:
    print(f"Database not available: {e}")
    DB_AVAILABLE = False
    SessionLocal = None

# Import storage for fallback
from utils.storage import meetings_db


def get_meeting_from_db_or_memory(meeting_id: str) -> Optional[Dict]:
    """Get meeting from database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                # Generate title from start_time for display
                title = None
                if meeting.start_time:
                    from datetime import datetime
                    title = f"Meeting {meeting.start_time.strftime('%Y-%m-%d %H:%M')}"
                
                result = {
                    "meeting_id": meeting.id,
                    "title": title,
                    "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                    "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                    "status": meeting.status,
                    "transcript": meeting.transcript or [],
                    "summary": meeting.summary,
                    "tasks": meeting.tasks or [],
                }
                db.close()
                return result
            db.close()
        except Exception as e:
            print(f"Error reading from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Fallback to in-memory
    return meetings_db.get(meeting_id)


def _extract_and_link_speakers(meeting_id: str, transcript: List[Dict], db):
    """Extract unique speakers from transcript and create/update speaker records"""
    if not transcript:
        return
    
    # Extract unique speaker names from transcript
    speaker_names = set()
    for segment in transcript:
        speaker_name = segment.get("speaker", "Unknown")
        if speaker_name and speaker_name != "Unknown":
            speaker_names.add(speaker_name)
    
    if not speaker_names:
        return  # No speakers to process
    
    print(f"[DB] Extracting speakers for meeting {meeting_id}: {speaker_names}")
    
    # Process each speaker - just ensure they exist in the database
    for speaker_name in speaker_names:
        # Find or create speaker
        speaker = db.query(Speaker).filter(Speaker.name == speaker_name).first()
        if not speaker:
            # Create new speaker (unknown user for now)
            speaker = Speaker(
                id=str(uuid.uuid4()),
                name=speaker_name,
                audio_reference=None,  # No audio reference for auto-detected speakers
            )
            db.add(speaker)
            db.flush()  # Flush to get the speaker ID
            print(f"[DB] Created new speaker: {speaker_name} (ID: {speaker.id})")
        else:
            print(f"[DB] Found existing speaker: {speaker_name} (ID: {speaker.id})")


def save_meeting_to_db(meeting_data: dict):
    """Save meeting to database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meeting = db.query(Meeting).filter(Meeting.id == meeting_data["meeting_id"]).first()
            
            if meeting:
                # Update existing
                meeting.start_time = datetime.fromisoformat(meeting_data["start_time"]) if meeting_data.get("start_time") else meeting.start_time
                meeting.end_time = datetime.fromisoformat(meeting_data["end_time"]) if meeting_data.get("end_time") else meeting.end_time
                meeting.status = meeting_data.get("status", meeting.status)
                meeting.transcript = meeting_data.get("transcript", meeting.transcript)
                meeting.summary = meeting_data.get("summary", meeting.summary)
                meeting.tasks = meeting_data.get("tasks", meeting.tasks)
                meeting.updated_at = datetime.utcnow()
            else:
                # Create new
                meeting = Meeting(
                    id=meeting_data["meeting_id"],
                    start_time=datetime.fromisoformat(meeting_data["start_time"]) if meeting_data.get("start_time") else datetime.utcnow(),
                    end_time=datetime.fromisoformat(meeting_data["end_time"]) if meeting_data.get("end_time") else None,
                    status=meeting_data.get("status", "active"),
                    transcript=meeting_data.get("transcript", []),
                    summary=meeting_data.get("summary"),
                    tasks=meeting_data.get("tasks", []),
                )
                db.add(meeting)
            
            # Extract and link speakers from transcript
            transcript = meeting_data.get("transcript", [])
            if transcript:
                _extract_and_link_speakers(meeting_data["meeting_id"], transcript, db)
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error saving to database: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    # Always update in-memory as well (for background tasks and fallback)
    meetings_db[meeting_data["meeting_id"]] = meeting_data


def get_all_meetings_from_db() -> List[Dict]:
    """Get all meetings from database or in-memory storage"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            meetings = db.query(Meeting).all()
            result = []
            for meeting in meetings:
                # Generate title from start_time for display
                title = None
                if meeting.start_time:
                    title = f"Meeting {meeting.start_time.strftime('%Y-%m-%d %H:%M')}"
                
                result.append({
                    "meeting_id": meeting.id,
                    "title": title,
                    "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                    "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                    "status": meeting.status,
                    "transcript": meeting.transcript or [],
                    "summary": meeting.summary,
                    "tasks": meeting.tasks or [],
                })
            db.close()
            return result
        except Exception as e:
            print(f"Error reading meetings from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Fallback to in-memory
    return list(meetings_db.values())


def get_meeting_speakers(meeting_id: str) -> List[Dict]:
    """Get all speakers for a meeting by extracting from transcript"""
    # Get meeting to extract speakers from transcript
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        return []
    
    transcript = meeting.get("transcript", [])
    if not transcript:
        return []
    
    # Extract unique speaker names from transcript
    speaker_names = set()
    for segment in transcript:
        speaker_name = segment.get("speaker", "Unknown")
        if speaker_name and speaker_name != "Unknown":
            speaker_names.add(speaker_name)
    
    if not speaker_names:
        return []
    
    # Try to get speaker details from database if available
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            speakers = []
            for speaker_name in speaker_names:
                speaker = db.query(Speaker).filter(Speaker.name == speaker_name).first()
                if speaker:
                    speakers.append({
                        "id": speaker.id,
                        "name": speaker.name,
                        "audio_reference": speaker.audio_reference,
                        "created_at": speaker.created_at.isoformat() if speaker.created_at else None,
                    })
                else:
                    # Speaker not in database, return basic info
                    speakers.append({
                        "id": None,
                        "name": speaker_name,
                        "audio_reference": None,
                        "created_at": None,
                    })
            db.close()
            return speakers
        except Exception as e:
            print(f"Error reading speakers from database: {e}")
            if 'db' in locals():
                db.close()
    
    # Fallback: return basic speaker info from transcript
    return [{"id": None, "name": name, "audio_reference": None, "created_at": None} 
            for name in speaker_names]


def get_speaker_meetings(speaker_id: str) -> List[str]:
    """Get all meeting IDs for a speaker by searching through meeting transcripts"""
    # First, get the speaker name from the database
    speaker_name = None
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
            if speaker:
                speaker_name = speaker.name
            db.close()
        except Exception as e:
            print(f"Error reading speaker from database: {e}")
            if 'db' in locals():
                db.close()
    
    if not speaker_name:
        return []
    
    # Search through all meetings to find where this speaker appears
    meetings = get_all_meetings_from_db()
    meeting_ids = []
    
    for meeting in meetings:
        transcript = meeting.get("transcript", [])
        for segment in transcript:
            if segment.get("speaker") == speaker_name:
                meeting_ids.append(meeting.get("meeting_id") or meeting.get("id"))
                break  # Found speaker in this meeting, move to next meeting
    
    return meeting_ids


def get_speaker_by_name(speaker_name: str) -> Optional[Dict]:
    """Get speaker by name"""
    if DB_AVAILABLE and SessionLocal:
        try:
            db = SessionLocal()
            speaker = db.query(Speaker).filter(Speaker.name == speaker_name).first()
            if speaker:
                result = {
                    "id": speaker.id,
                    "name": speaker.name,
                    "audio_reference": speaker.audio_reference,
                    "created_at": speaker.created_at.isoformat() if speaker.created_at else None,
                }
                db.close()
                return result
            db.close()
        except Exception as e:
            print(f"Error reading speaker from database: {e}")
            if 'db' in locals():
                db.close()
    
    return None


def merge_diarized_transcripts(meeting_id: str, diarized_segments: List[Dict]) -> bool:
    """
    Merge diarized transcript segments with existing transcripts, replacing "Unknown" speakers
    
    Args:
        meeting_id: Meeting identifier
        diarized_segments: List of diarized segments with speaker information
        
    Returns:
        True if merge was successful, False otherwise
    """
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        print(f"[DB] ⚠️  Meeting {meeting_id} not found for diarization merge")
        return False
    
    transcript = meeting.get("transcript", [])
    if not transcript:
        # If no transcripts exist yet, add diarized segments as new entries
        # This can happen if batch processing runs before realtime transcripts are saved
        print(f"[DB] [Diarization] ℹ️  No existing transcript, adding {len(diarized_segments)} diarized segments as new entries", flush=True)
        
        # Add diarized segments directly to transcript
        # Note: We add even "Unknown" speakers because they still have transcription text
        # and can be merged with realtime transcripts later
        from datetime import datetime
        speakers_added = set()
        for diarized_seg in diarized_segments:
            speaker = diarized_seg.get("speaker", "Unknown")
            text = diarized_seg.get("text", "")
            
            # Only skip if text is empty
            if not text:
                continue
                
            transcript_entry = {
                "text": text,
                "speaker": speaker,
                "start": diarized_seg.get("start", 0.0),
                "end": diarized_seg.get("end", 0.0),
                "timestamp": datetime.now().isoformat(),
            }
            transcript.append(transcript_entry)
            speakers_added.add(speaker)
        
        if transcript:
            meeting["transcript"] = transcript
            save_meeting_to_db(meeting)
            print(f"[DB] [Diarization] ✅ Added {len(transcript)} segments with {len(speakers_added)} speakers: {speakers_added}", flush=True)
            return True
        else:
            print(f"[DB] [Diarization] ⚠️  No valid diarized segments to add")
            return False
    
    if not diarized_segments:
        print(f"[DB] ⚠️  No diarized segments to merge for meeting {meeting_id}")
        return False
    
    print(f"[DB] [Diarization] 🔄 Merging {len(diarized_segments)} diarized segments with {len(transcript)} existing segments", flush=True)
    
    # Create a mapping of time ranges to diarized segments
    # We'll match by time overlap
    updated_count = 0
    speakers_found = set()
    
    for diarized_seg in diarized_segments:
        diarized_start = diarized_seg.get("start", 0.0)
        diarized_end = diarized_seg.get("end", 0.0)
        diarized_speaker = diarized_seg.get("speaker", "Unknown")
        diarized_text = diarized_seg.get("text", "")
        
        if diarized_speaker == "Unknown":
            continue  # Skip if diarization didn't identify speaker
        
        # Find matching transcript segments by time overlap
        # Match segments that overlap in time and have "Unknown" speaker
        for existing_seg in transcript:
            existing_start = existing_seg.get("start", 0.0)
            existing_end = existing_seg.get("end", 0.0)
            existing_speaker = existing_seg.get("speaker", "Unknown")
            
            # Only update "Unknown" speaker segments
            if existing_speaker != "Unknown":
                continue
            
            # Check for time overlap (with some tolerance)
            # Consider overlap if segments are within 2 seconds of each other
            tolerance = 2.0
            if (diarized_start <= existing_end + tolerance and 
                diarized_end >= existing_start - tolerance):
                
                # Check if text is similar (fuzzy match)
                # Simple check: if texts share significant words
                existing_text = existing_seg.get("text", "")
                if existing_text and diarized_text:
                    # Simple similarity: check if they share at least 30% of words
                    existing_words = set(existing_text.lower().split())
                    diarized_words = set(diarized_text.lower().split())
                    if existing_words and diarized_words:
                        similarity = len(existing_words & diarized_words) / max(len(existing_words), len(diarized_words))
                        if similarity >= 0.3:  # At least 30% word overlap
                            # Update the speaker
                            existing_seg["speaker"] = diarized_speaker
                            updated_count += 1
                            speakers_found.add(diarized_speaker)
                            break  # Match found, move to next diarized segment
    
    if updated_count > 0:
        print(f"[DB] [Diarization] ✅ Merged {updated_count} segments with {len(speakers_found)} speakers: {speakers_found}", flush=True)
        # Save updated meeting
        save_meeting_to_db(meeting)
        return True
    else:
        print(f"[DB] [Diarization] ⚠️  No segments matched for merging", flush=True)
        return False

