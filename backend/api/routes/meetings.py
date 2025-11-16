"""
Meeting management endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional
import uuid
import asyncio

from services.llm_service import llm_service
from services.stt_service import stt_service
from services.tts_service import tts_service
from services.websocket_manager import websocket_manager
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db, get_all_meetings_from_db, merge_diarized_transcripts, DB_AVAILABLE
# DISABLED: speaker functions (no diarization, no need for speakers)
# from utils.db_helpers import get_meeting_speakers, get_speakers_for_meetings_batch
from utils.storage import meetings_db, audio_streams, background_tasks
from services.background_tasks import process_summary_update, process_task_extraction, process_batch_diarization
from models.database import Task, SessionLocal

router = APIRouter()


@router.post("/api/meetings/start")
async def start_meeting():
    """Start a new meeting session"""
    meeting_id = str(uuid.uuid4())
    meeting_data = {
        "meeting_id": meeting_id,
        "start_time": datetime.now().isoformat(),
        "status": "active",
        "transcript": [],
        "summary": None,
        "tasks": [],
    }
    
    # Save to database
    save_meeting_to_db(meeting_data)
    audio_streams[meeting_id] = []
    
    # Start background tasks
    summary_task = asyncio.create_task(process_summary_update(meeting_id))
    task_extraction_task = asyncio.create_task(process_task_extraction(meeting_id))
    # DISABLED: Batch diarization on stand-by (keeping for later)
    # batch_diarization_task = asyncio.create_task(process_batch_diarization(meeting_id))
    background_tasks[meeting_id] = {
        "summary": summary_task,
        "task_extraction": task_extraction_task,
        # "batch_diarization": batch_diarization_task,
    }
    
    # Broadcast meeting started
    await websocket_manager.send_status_update(
        meeting_id=meeting_id,
        status="started",
        message="Meeting started"
    )
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "status": "started",
        "start_time": meeting_data["start_time"],
    })


@router.post("/api/meetings/{meeting_id}/stop")
async def stop_meeting(meeting_id: str):
    """Stop a meeting session and generate final summary"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting["status"] = "completed"
    meeting["end_time"] = datetime.now().isoformat()
    
    # Cancel background tasks
    if meeting_id in background_tasks:
        for task in background_tasks[meeting_id].values():
            task.cancel()
        del background_tasks[meeting_id]
    
    # Get initial transcript count to detect new transcripts after commit
    initial_transcript_count = len(meeting.get("transcript", []))
    print(f"[Meetings] 📊 Initial transcript count: {initial_transcript_count}")
    
    # Commit any pending realtime transcripts before processing buffers
    # Note: The websocket handler may have already committed when it received "end_stream",
    # but we'll try here too in case the websocket closed before that happened
    try:
        committed = await stt_service.commit_realtime_transcript(meeting_id)
        if committed:
            print(f"[Meetings] ✅ Committed pending realtime transcripts for meeting {meeting_id}")
            # Wait a bit for the realtime API to send the final committed transcript
            # This gives time for any pending audio to be transcribed and sent
            import asyncio
            # Wait up to 2 seconds, checking every 0.2 seconds if new transcripts arrived
            for _ in range(10):  # 10 * 0.2 = 2 seconds max
                await asyncio.sleep(0.2)
                # Reload meeting to check for new transcripts
                current_meeting = get_meeting_from_db_or_memory(meeting_id)
                if current_meeting:
                    current_count = len(current_meeting.get("transcript", []))
                    if current_count > initial_transcript_count:
                        print(f"[Meetings] ✅ Received {current_count - initial_transcript_count} new transcript(s) after commit")
                        break
            else:
                print(f"[Meetings] ⏳ Waited 2 seconds for final realtime transcript (no new transcripts detected)")
        else:
            print(f"[Meetings] ℹ️  No realtime connection to commit for meeting {meeting_id} (may have already been committed/disconnected)")
            # Even if we couldn't commit (connection already closed), wait a bit in case
            # the websocket handler already committed and transcripts are still arriving
            import asyncio
            await asyncio.sleep(0.5)  # Brief wait in case websocket handler committed
    except Exception as e:
        print(f"[Meetings] ⚠️  Could not commit realtime transcripts: {e}")
        # Even on error, wait a bit in case websocket handler already committed
        import asyncio
        await asyncio.sleep(0.5)
        import traceback
        traceback.print_exc()
    
    # Process any remaining STT buffers before clearing them
    print(f"[Meetings] 🔄 Processing remaining STT buffers for meeting {meeting_id}...")
    
    # Callback to save transcripts to database
    async def save_transcript_callback(result: dict, meeting_id: str):
        """Callback to save transcription results to database"""
        try:
            if not result.get("success"):
                return
            
            meeting = get_meeting_from_db_or_memory(meeting_id)
            if not meeting:
                return
            
            segments = result.get("segments", [])
            if not segments:
                return
            
            # Add each segment to the transcript
            for segment in segments:
                transcript_entry = {
                    "text": segment["text"],
                    # DISABLED: speaker field (no diarization, no need for speakers)
                    # "speaker": segment.get("speaker", "Unknown"),
                    "start": segment.get("start", 0.0),
                    "end": segment.get("end", 0.0),
                    "timestamp": datetime.now().isoformat(),
                }
                meeting["transcript"].append(transcript_entry)
            
            # Save to database
            save_meeting_to_db(meeting)
            print(f"[Meetings] ✅ Saved {len(segments)} transcript segments to database")
            
            # Broadcast transcript updates
            for segment in segments:
                transcript_entry = {
                    "text": segment["text"],
                    # DISABLED: speaker field (no diarization, no need for speakers)
                    # "speaker": segment.get("speaker", "Unknown"),
                    "start": segment.get("start", 0.0),
                    "end": segment.get("end", 0.0),
                    "timestamp": datetime.now().isoformat(),
                }
                await websocket_manager.send_transcript_update(
                    meeting_id=meeting_id,
                    transcript_entry=transcript_entry
                )
        except Exception as e:
            print(f"[Meetings] ❌ Error in save_transcript_callback: {e}")
            import traceback
            traceback.print_exc()
    
    # Process remaining buffers
    buffer_results = await stt_service.process_remaining_buffers(
        meeting_id=meeting_id,
        callback=save_transcript_callback
    )
    
    if buffer_results.get("streaming_processed") or buffer_results.get("batch_processed"):
        total_segments = buffer_results.get("streaming_segments", 0) + buffer_results.get("batch_segments", 0)
        print(f"[Meetings] ✅ Processed {total_segments} final transcript segments from buffers")
    
    if buffer_results.get("errors"):
        print(f"[Meetings] ⚠️  Some errors occurred while processing buffers: {buffer_results['errors']}")
    
    # Clear batch buffer (cleanup after processing)
    stt_service.clear_batch_buffer(meeting_id)
    
    # Reload meeting to get latest transcript (in case callback updated it)
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found after processing buffers")
    
    # Update status and end_time again (in case meeting was reloaded)
    meeting["status"] = "completed"
    meeting["end_time"] = datetime.now().isoformat()
    
    # Generate final summary if not exists
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
            # Save title if provided
            if result.get("title"):
                meeting["title"] = result["title"]
    
    # Extract tasks using OpenAI API
    extracted_task_ids = []
    if meeting.get("transcript") and len(meeting["transcript"]) > 0:
        print(f"[Meetings] 🔄 Extracting tasks using OpenAI for meeting {meeting_id}...", flush=True)
        # Get existing tasks from database to avoid duplicates
        existing_tasks_list = []
        if SessionLocal:
            try:
                db = SessionLocal()
                existing_db_tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()
                for task in existing_db_tasks:
                    existing_tasks_list.append({
                        "description": task.description,
                        "title": task.title,
                    })
                db.close()
            except Exception as e:
                print(f"[Meetings] ⚠️  Error getting existing tasks: {e}", flush=True)
                if 'db' in locals():
                    db.close()
        
        task_result = await llm_service.extract_tasks(
            transcript=meeting["transcript"],
            existing_tasks=existing_tasks_list
        )
        
        if task_result["success"] and task_result.get("tasks"):
            # Get existing task IDs from database to avoid duplicates
            existing_db_task_ids = set()
            if SessionLocal:
                try:
                    db = SessionLocal()
                    existing_tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()
                    existing_db_task_ids = {t.id for t in existing_tasks}
                    db.close()
                except Exception as e:
                    print(f"[Meetings] ⚠️  Error checking existing tasks: {e}", flush=True)
                    if 'db' in locals():
                        db.close()
            
            # Save each extracted task to the database
            for task_data in task_result["tasks"]:
                try:
                    # Generate task ID
                    task_id = str(uuid.uuid4())
                    
                    # Check for duplicates by description (basic check)
                    # In the future, we could add more sophisticated duplicate detection
                    task_description = task_data.get("description", "").lower().strip()
                    is_duplicate = False
                    if SessionLocal and task_description:
                        try:
                            db = SessionLocal()
                            existing_task = db.query(Task).filter(
                                Task.meeting_id == meeting_id,
                                Task.description.ilike(f"%{task_description[:50]}%")
                            ).first()
                            if existing_task:
                                is_duplicate = True
                            db.close()
                        except Exception:
                            if 'db' in locals():
                                db.close()
                    
                    if is_duplicate:
                        print(f"[Meetings] ⏭️  Skipping duplicate task: {task_description[:50]}", flush=True)
                        continue
                    
                    # Parse due_date if provided
                    due_date = None
                    if task_data.get("due_date"):
                        try:
                            from datetime import datetime as dt
                            due_date_str = task_data["due_date"]
                            # Handle different date formats
                            if "T" in due_date_str:
                                # ISO format with time
                                due_date = dt.fromisoformat(due_date_str.replace("Z", "+00:00"))
                            else:
                                # Just date (YYYY-MM-DD)
                                due_date = dt.strptime(due_date_str, "%Y-%m-%d")
                        except Exception as e:
                            # If parsing fails, leave as None
                            print(f"[Meetings] ⚠️  Could not parse due_date '{task_data.get('due_date')}': {e}", flush=True)
                            due_date = None
                    
                    # Save to database
                    if SessionLocal:
                        try:
                            db = SessionLocal()
                            new_task = Task(
                                id=task_id,
                                meeting_id=meeting_id,
                                title=task_data.get("title", task_data.get("description", "")[:100]),
                                description=task_data.get("description", ""),
                                assignee=task_data.get("assignee"),
                                due_date=due_date,
                                status="pending",
                                priority=task_data.get("priority", "medium"),
                            )
                            db.add(new_task)
                            db.commit()
                            db.close()
                            
                            extracted_task_ids.append(task_id)
                            print(f"[Meetings] ✅ Saved task to database: {task_id} - {task_data.get('title', '')[:50]}", flush=True)
                        except Exception as e:
                            print(f"[Meetings] ❌ Error saving task to database: {e}", flush=True)
                            import traceback
                            traceback.print_exc()
                            if 'db' in locals():
                                db.rollback()
                                db.close()
                    else:
                        # Fallback: if database not available, still add to meeting's tasks JSON
                        # but this shouldn't happen in production
                        print(f"[Meetings] ⚠️  Database not available, cannot save task", flush=True)
                        
                except Exception as e:
                    print(f"[Meetings] ❌ Error processing extracted task: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
            
            # Update meeting's tasks JSON to only contain task_ids
            # Get all task IDs from database for this meeting
            if SessionLocal:
                try:
                    db = SessionLocal()
                    all_tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()
                    meeting["tasks"] = [{"task_id": t.id} for t in all_tasks]
                    db.close()
                except Exception as e:
                    print(f"[Meetings] ⚠️  Error updating meeting tasks JSON: {e}", flush=True)
                    if 'db' in locals():
                        db.close()
            
            # Broadcast task update via WebSocket
            if extracted_task_ids:
                await websocket_manager.send_tasks_update(
                    meeting_id=meeting_id,
                    tasks=meeting.get("tasks", [])
                )
                print(f"[Meetings] ✅ Extracted and saved {len(extracted_task_ids)} tasks using OpenAI", flush=True)
        elif not task_result["success"]:
            error = task_result.get("error", "Unknown error")
            print(f"[Meetings] ⚠️  Failed to extract tasks with OpenAI: {error}", flush=True)
        else:
            print(f"[Meetings] ℹ️  No tasks extracted from meeting transcript", flush=True)
    
    # Save to database
    save_meeting_to_db(meeting)
    
    # Broadcast meeting ended
    await websocket_manager.send_status_update(
        meeting_id=meeting_id,
        status="completed",
        message="Meeting ended"
    )
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "status": "completed",
        "end_time": meeting["end_time"],
        "summary": meeting.get("summary"),
        "tasks_extracted": len(extracted_task_ids),
    })


@router.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get meeting details"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # DISABLED: Get speakers for this meeting (no diarization, no need for speakers)
    # speakers = get_meeting_speakers(meeting_id)
    # meeting_with_speakers = meeting.copy()
    # meeting_with_speakers["speakers"] = speakers
    # return JSONResponse(content=meeting_with_speakers)
    
    return JSONResponse(content=meeting)


@router.get("/api/meetings")
async def get_meetings():
    """Get all meetings (history) - optimized to avoid loading full transcripts"""
    # Get meetings without full data (faster)
    meetings = get_all_meetings_from_db(include_full_data=False)
    
    # DISABLED: Speaker extraction (no diarization, no need for speakers)
    # To get speakers, we need transcripts but don't want to load full data
    # So we'll fetch transcripts separately and batch process speakers
    # if DB_AVAILABLE:
    #     try:
    #         from models.database import Meeting, SessionLocal
    #         if SessionLocal:
    #             db = SessionLocal()
    #             # Get just transcripts for speaker extraction (not full meeting data)
    #             meeting_ids = [m.get("meeting_id") for m in meetings if m.get("meeting_id")]
    #             if meeting_ids:
    #                 # Query only transcript column for these meetings
    #                 meetings_with_transcripts = db.query(
    #                     Meeting.id, Meeting.transcript
    #                 ).filter(Meeting.id.in_(meeting_ids)).all()
    #                 
    #                 # Build transcript map
    #                 transcript_map = {m.id: (m.transcript or []) for m in meetings_with_transcripts}
    #                 
    #                 # Batch get speakers for all meetings
    #                 speakers_map = get_speakers_for_meetings_batch(transcript_map)
    #                 
    #                 # Add speakers to meetings
    #                 for meeting in meetings:
    #                     meeting_id = meeting.get("meeting_id")
    #                     if meeting_id:
    #                         meeting["speakers"] = speakers_map.get(meeting_id, [])
    #                 
    #                 db.close()
    #             else:
    #                 # No meetings, add empty speakers
    #                 for meeting in meetings:
    #                     meeting["speakers"] = []
    #     except Exception as e:
    #         print(f"Error loading speakers for meetings: {e}")
    #         # Fallback: add empty speakers
    #         for meeting in meetings:
    #             meeting["speakers"] = []
    # else:
    #     # Fallback: try to get speakers individually (slower but works)
    #     for meeting in meetings:
    #         meeting_id = meeting.get("meeting_id")
    #         if meeting_id:
    #             speakers = get_meeting_speakers(meeting_id)
    #             meeting["speakers"] = speakers
    
    return JSONResponse(content={"meetings": meetings})


@router.get("/api/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    """Get current meeting summary (real-time updates)"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Trigger summary generation if not exists and we have transcript
    if not meeting.get("summary") and meeting.get("transcript"):
        result = await llm_service.summarize_meeting(
            transcript=meeting["transcript"],
            incremental=False
        )
        if result["success"]:
            meeting["summary"] = result["summary"]
            # Save title if provided
            if result.get("title"):
                meeting["title"] = result["title"]
            save_meeting_to_db(meeting)
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "summary": meeting.get("summary") or "Summary will be available shortly...",
        "last_updated": meeting.get("end_time") or meeting["start_time"],
    })


@router.get("/api/meetings/active")
async def get_active_meeting():
    """Get the current active meeting ID"""
    # Find active meeting in database
    try:
        from models.database import Meeting, SessionLocal
        if SessionLocal:
            db = SessionLocal()
            active_meeting = db.query(Meeting).filter(Meeting.status == "active").first()
            db.close()
            
            if active_meeting:
                return JSONResponse(content={
                    "meeting_id": active_meeting.id,
                    "status": "active",
                    "start_time": active_meeting.start_time.isoformat() if active_meeting.start_time else None,
                })
        
        # Fallback: check in-memory storage
        for meeting_id, meeting_data in meetings_db.items():
            if meeting_data.get("status") == "active":
                return JSONResponse(content={
                    "meeting_id": meeting_id,
                    "status": "active",
                    "start_time": meeting_data.get("start_time"),
                })
        
        return JSONResponse(content={"meeting_id": None, "status": "no_active_meeting"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active meeting: {str(e)}")


@router.get("/api/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(meeting_id: str):
    """Get meeting transcript"""
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return JSONResponse(content={
        "meeting_id": meeting_id,
        "transcript": meeting.get("transcript", []),
    })


@router.get("/api/voices")
async def get_voices():
    """Get list of available voices from ElevenLabs"""
    result = tts_service.get_voices()
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to fetch voices")
        )
    
    return JSONResponse(content={
        "success": True,
        "voices": result["voices"]
    })


@router.post("/api/meetings/{meeting_id}/audio/generate")
async def generate_meeting_audio(
    meeting_id: str, 
    audio_type: str = Query("summary", description="Type of audio to generate: 'summary' or 'transcript'"),
    voice_id: Optional[str] = Query(None, description="Voice ID to use for TTS (uses first available if not provided)")
):
    """
    Generate audio from meeting transcript or summary using ElevenLabs TTS
    
    Args:
        meeting_id: Meeting ID
        audio_type: "summary" or "transcript" (default: "summary")
        voice_id: Optional voice ID (uses first available if not provided)
    """
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    try:
        # If no voice_id provided, get the first available voice
        if not voice_id:
            voices_result = tts_service.get_voices()
            if voices_result["success"] and len(voices_result["voices"]) > 0:
                voice_id = voices_result["voices"][0]["voice_id"]
            else:
                # Fallback to default
                voice_id = None
        
        if audio_type == "summary":
            summary = meeting.get("summary")
            if not summary:
                raise HTTPException(
                    status_code=400,
                    detail="Meeting summary not available. Please wait for summary generation."
                )
            
            result = tts_service.generate_audio(
                text=summary,
                meeting_id=meeting_id,
                audio_type="summary",
                voice_id=voice_id
            )
            
        elif audio_type == "transcript":
            transcript = meeting.get("transcript", [])
            if not transcript or len(transcript) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Meeting transcript is empty"
                )
            
            result = tts_service.generate_transcript_audio(
                transcript=transcript,
                meeting_id=meeting_id,
                voice_id=voice_id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid audio_type. Must be 'summary' or 'transcript'"
            )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to generate audio")
            )
        
        return JSONResponse(content={
            "success": True,
            "meeting_id": meeting_id,
            "audio_type": audio_type,
            "filename": result["filename"],
            "audio_url": result["relative_path"],
            "message": f"Audio generated successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Meetings] ❌ Error generating audio: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate audio: {str(e)}"
        )

