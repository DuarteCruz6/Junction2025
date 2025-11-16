"""
Background processing tasks for meetings
"""

import asyncio
import uuid
from datetime import datetime

from services.llm_service import llm_service
from services.stt_service import stt_service
from services.websocket_manager import websocket_manager
from utils.storage import meetings_db
from utils.db_helpers import save_meeting_to_db, merge_diarized_transcripts, get_meeting_from_db_or_memory
from models.database import Reminder, SessionLocal


async def process_summary_update(meeting_id: str):
    """Background task to periodically update meeting summary"""
    print(f"[Background] [Summary] 🚀 Starting summary update task for meeting {meeting_id}", flush=True)
    
    # Keep running while meeting is active (check both memory and database)
    while True:
        try:
            # Try to get meeting from memory first, then database
            meeting = meetings_db.get(meeting_id)
            if not meeting:
                meeting = get_meeting_from_db_or_memory(meeting_id)
                # If found in database, also update memory for faster access
                if meeting:
                    meetings_db[meeting_id] = meeting
            
            # Check if meeting exists and is active
            if not meeting:
                print(f"[Background] [Summary] ⚠️  Meeting {meeting_id} not found, stopping task", flush=True)
                break
            
            if meeting.get("status") != "active":
                print(f"[Background] [Summary] ⏸️  Meeting {meeting_id} is not active (status: {meeting.get('status')}), stopping task", flush=True)
                break
            
            transcript = meeting.get("transcript", [])
            
            # Only update if we have new transcript segments (at least 3)
            if len(transcript) >= 3:
                previous_summary = meeting.get("summary")
                
                print(f"[Background] [Summary] 🔄 Generating summary for meeting {meeting_id} ({len(transcript)} transcript segments)", flush=True)
                
                # Generate summary using LLM
                result = await llm_service.summarize_meeting(
                    transcript=transcript,
                    previous_summary=previous_summary,
                    incremental=True
                )
                
                if result["success"]:
                    meeting["summary"] = result["summary"]
                    # Only update title if it doesn't exist yet and title is provided
                    # (incremental updates don't generate new titles)
                    if result.get("title") and not meeting.get("title"):
                        meeting["title"] = result["title"]
                    
                    # Save to database
                    save_meeting_to_db(meeting)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_summary_update(
                        meeting_id=meeting_id,
                        summary=result["summary"]
                    )
                    print(f"[Background] [Summary] ✅ Summary updated for meeting {meeting_id}", flush=True)
                else:
                    error = result.get("error", "Unknown error")
                    print(f"[Background] [Summary] ❌ Failed to generate summary for meeting {meeting_id}: {error}", flush=True)
            else:
                # Log why we're not generating (but only occasionally to avoid spam)
                if len(transcript) > 0:
                    print(f"[Background] [Summary] ⏸️  Waiting for more transcript segments ({len(transcript)}/3) for meeting {meeting_id}", flush=True)
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"[Background] [Summary] ❌ Error in summary update task for {meeting_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await asyncio.sleep(30)


async def process_task_extraction(meeting_id: str):
    """Background task to periodically extract tasks"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            existing_tasks = meeting.get("tasks", [])
            
            # Only extract if we have transcript segments
            if len(transcript) >= 5:  # Need some content to extract tasks
                result = await llm_service.extract_tasks(
                    transcript=transcript,
                    existing_tasks=existing_tasks
                )
                
                if result["success"] and result["tasks"]:
                    # Add new tasks
                    for task in result["tasks"]:
                        task_id = str(uuid.uuid4())
                        task_data = {
                            "task_id": task_id,
                            "description": task.get("description", ""),
                            "assignee": task.get("assignee"),
                            "due_date": task.get("due_date"),
                            "status": "pending",
                            "priority": task.get("priority", "medium"),
                            "created_at": datetime.now().isoformat(),
                        }
                        meeting["tasks"].append(task_data)
                    
                    # Save to database
                    save_meeting_to_db(meeting)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_tasks_update(
                        meeting_id=meeting_id,
                        tasks=meeting["tasks"]
                    )
            
            # Wait 60 seconds before next extraction
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Error in task extraction task for {meeting_id}: {e}")
            await asyncio.sleep(60)


async def process_reminder_extraction(meeting_id: str):
    """Background task to periodically extract reminders from family calls (for elderly care)"""
    print(f"[Background] [Reminders] 🚀 Starting reminder extraction task for meeting {meeting_id}", flush=True)
    
    while True:
        try:
            # Try to get meeting from memory first, then database
            meeting = meetings_db.get(meeting_id)
            if not meeting:
                meeting = get_meeting_from_db_or_memory(meeting_id)
                if meeting:
                    meetings_db[meeting_id] = meeting
            
            # Check if meeting exists and is active
            if not meeting:
                print(f"[Background] [Reminders] ⚠️  Meeting {meeting_id} not found, stopping task", flush=True)
                break
            
            if meeting.get("status") != "active":
                print(f"[Background] [Reminders] ⏸️  Meeting {meeting_id} is not active (status: {meeting.get('status')}), stopping task", flush=True)
                break
            
            transcript = meeting.get("transcript", [])
            
            # Get existing reminders from database
            existing_reminders = []
            if SessionLocal:
                try:
                    db = SessionLocal()
                    reminders_from_db = db.query(Reminder).filter(Reminder.meeting_id == meeting_id).all()
                    for reminder in reminders_from_db:
                        existing_reminders.append({
                            "description": reminder.description,
                            "title": reminder.title,
                        })
                    db.close()
                except Exception as e:
                    print(f"[Background] [Reminders] Error getting existing reminders: {e}")
                    if 'db' in locals():
                        db.close()
            
            # Only extract if we have transcript segments
            if len(transcript) >= 5:  # Need some content to extract reminders
                print(f"[Background] [Reminders] 🔄 Extracting reminders for meeting {meeting_id} ({len(transcript)} transcript segments)", flush=True)
                
                result = await llm_service.extract_reminders(
                    transcript=transcript,
                    existing_reminders=existing_reminders
                )
                
                if result["success"] and result["reminders"]:
                    # Save new reminders to database
                    new_reminders = []
                    for reminder in result["reminders"]:
                        reminder_id = str(uuid.uuid4())
                        
                        # Parse reminder_date if provided as string
                        reminder_date = None
                        if reminder.get("reminder_date"):
                            try:
                                from datetime import datetime
                                # Try ISO format first
                                reminder_date = datetime.fromisoformat(reminder["reminder_date"].replace("Z", "+00:00"))
                            except Exception:
                                try:
                                    # Try common date formats
                                    from datetime import datetime
                                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                                        try:
                                            reminder_date = datetime.strptime(reminder["reminder_date"], fmt)
                                            break
                                        except ValueError:
                                            continue
                                    if reminder_date is None:
                                        print(f"[Background] [Reminders] Could not parse reminder_date: {reminder['reminder_date']}")
                                except Exception as e:
                                    print(f"[Background] [Reminders] Error parsing reminder_date: {e}")
                        
                        reminder_data = {
                            "reminder_id": reminder_id,
                            "title": reminder.get("title"),
                            "description": reminder.get("description", ""),
                            "reminder_date": reminder_date,
                            "reminder_time": reminder.get("reminder_time"),
                            "is_recurring": reminder.get("is_recurring", False),
                            "recurrence_pattern": reminder.get("recurrence_pattern"),
                            "status": "active",
                            "priority": reminder.get("priority", "medium"),
                            "created_at": datetime.now().isoformat(),
                        }
                        
                        # Save to database
                        if SessionLocal:
                            try:
                                db = SessionLocal()
                                db_reminder = Reminder(
                                    id=reminder_id,
                                    meeting_id=meeting_id,
                                    title=reminder_data["title"],
                                    description=reminder_data["description"],
                                    reminder_date=reminder_date,
                                    reminder_time=reminder_data["reminder_time"],
                                    is_recurring=reminder_data["is_recurring"],
                                    recurrence_pattern=reminder_data["recurrence_pattern"],
                                    status="active",
                                    priority=reminder_data["priority"],
                                )
                                db.add(db_reminder)
                                db.commit()
                                db.refresh(db_reminder)
                                db.close()
                            except Exception as e:
                                print(f"[Background] [Reminders] Error saving reminder to database: {e}")
                                if 'db' in locals():
                                    db.rollback()
                                    db.close()
                        
                        new_reminders.append(reminder_data)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_reminders_update(
                        meeting_id=meeting_id,
                        reminders=new_reminders
                    )
                    print(f"[Background] [Reminders] ✅ Extracted {len(new_reminders)} reminders for meeting {meeting_id}", flush=True)
                elif not result["success"]:
                    error = result.get("error", "Unknown error")
                    print(f"[Background] [Reminders] ❌ Failed to extract reminders for meeting {meeting_id}: {error}", flush=True)
            
            # Wait 60 seconds before next extraction
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"[Background] [Reminders] ❌ Error in reminder extraction task for {meeting_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await asyncio.sleep(60)


async def process_batch_diarization(meeting_id: str):
    """Background task to periodically process audio with speaker diarization
    
    DISABLED: Diarization is on stand-by. This function is kept for later re-enablement.
    """
    # DISABLED: Diarization on stand-by - keeping function structure for later
    print(f"[Background] [Diarization] ⏸️  Batch diarization task disabled (on stand-by) for meeting {meeting_id}", flush=True)
    # Wait indefinitely (task will be cancelled when meeting ends)
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        await asyncio.sleep(60)  # Sleep to avoid busy loop
    
    # ORIGINAL CODE (commented out for later re-enablement):
    # print(f"[Background] [Diarization] 🚀 Starting batch diarization task for meeting {meeting_id}", flush=True)
    # while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
    #     try:
    #         # Process batch buffer with diarization (runs every ~1 minute if conditions are met)
    #         result = await stt_service.process_batch_buffer_with_diarization(
    #             meeting_id=meeting_id,
    #             force=False
    #         )
    #         
    #         if result:
    #             if result.get("success"):
    #                 segments = result.get("segments", [])
    #                 if segments:
    #                     speakers = set(seg.get('speaker', 'Unknown') for seg in segments)
    #                     print(f"[Background] [Diarization] ✅ Processed {len(segments)} segments, {len(speakers)} speakers: {speakers}", flush=True)
    #                     
    #                     # Merge diarized results with existing transcripts (or add as new if no transcripts exist)
    #                     merge_success = merge_diarized_transcripts(meeting_id, segments)
    #                     if merge_success:
    #                         print(f"[Background] [Diarization] ✅ Merged diarized speakers into database for meeting {meeting_id}", flush=True)
    #                     # Don't log failure as error - it's expected if no transcripts exist yet or no matches found
    #             else:
    #                 error = result.get("error", "Unknown error")
    #                 print(f"[Background] [Diarization] ❌ Batch diarization failed for meeting {meeting_id}: {error}", flush=True)
    #         # else: result is None, which means conditions weren't met (logged in stt_service)
    #         
    #         # Check every 5 seconds for faster response to silence detection
    #         # The actual processing happens when conditions are met (silence + enough audio)
    #         await asyncio.sleep(5)
    #         
    #     except Exception as e:
    #         print(f"[Background] Error in batch diarization task for {meeting_id}: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         await asyncio.sleep(30)

