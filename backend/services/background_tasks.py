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


async def process_summary_update(meeting_id: str):
    """Background task to periodically update meeting summary"""
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            meeting = meetings_db[meeting_id]
            transcript = meeting.get("transcript", [])
            
            # Only update if we have new transcript segments (at least 3)
            if len(transcript) >= 3:
                previous_summary = meeting.get("summary")
                
                # Generate summary using LLM
                result = await llm_service.summarize_meeting(
                    transcript=transcript,
                    previous_summary=previous_summary,
                    incremental=True
                )
                
                if result["success"]:
                    meeting["summary"] = result["summary"]
                    
                    # Save to database
                    save_meeting_to_db(meeting)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_summary_update(
                        meeting_id=meeting_id,
                        summary=result["summary"]
                    )
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in summary update task for {meeting_id}: {e}")
            await asyncio.sleep(30)


def _ends_with_sentence_boundary(text: str) -> bool:
    """Check if text ends with a sentence boundary (period, exclamation, question mark)"""
    if not text:
        return False
    text = text.strip()
    return text.endswith('.') or text.endswith('!') or text.endswith('?') or text.endswith('。')


async def process_task_extraction(meeting_id: str):
    """Background task to periodically extract tasks (every 15 seconds, respecting sentence boundaries)"""
    import time
    print(f"[Task Extraction] 🚀 Starting task extraction background task for meeting {meeting_id}", flush=True)
    last_extraction_time = time.time()
    
    # Keep running while meeting exists and is active
    while True:
        # Check if meeting exists and is active
        meeting = get_meeting_from_db_or_memory(meeting_id)
        if not meeting or meeting.get("status") != "active":
            print(f"[Task Extraction] ⏸️  Meeting {meeting_id} no longer exists or is not active, stopping task extraction", flush=True)
            break
        try:
            current_time = time.time()
            time_since_last_extraction = current_time - last_extraction_time
            
            # Only extract if 15 seconds have passed
            if time_since_last_extraction < 15.0:
                await asyncio.sleep(1)  # Check every second
                continue
            
            print(f"[Task Extraction] ⏰ 15 seconds elapsed, checking for task extraction (meeting: {meeting_id})", flush=True)
            
            # Always get the latest meeting data from database or memory
            meeting = get_meeting_from_db_or_memory(meeting_id)
            if not meeting:
                print(f"[Task Extraction] ⚠️  Meeting {meeting_id} not found, skipping", flush=True)
                await asyncio.sleep(15)
                continue
            
            # Check if meeting is still active
            if meeting.get("status") != "active":
                print(f"[Task Extraction] ⏸️  Meeting {meeting_id} is not active (status: {meeting.get('status')}), stopping", flush=True)
                break
            
            transcript = meeting.get("transcript", [])
            existing_tasks = meeting.get("tasks", [])
            
            print(f"[Task Extraction] 📊 Meeting state - Transcript segments: {len(transcript)}, Existing tasks: {len(existing_tasks)}", flush=True)
            
            # Only extract if we have transcript segments (reduced to 1 to allow single-sentence tasks)
            if len(transcript) >= 1:  # Need at least one segment to extract tasks
                # Check if the last transcript segment ends with a sentence boundary
                # This prevents interrupting mid-sentence
                last_segment = transcript[-1] if transcript else None
                if last_segment:
                    last_text = last_segment.get("text", "")
                    has_boundary = _ends_with_sentence_boundary(last_text)
                    print(f"[Task Extraction] 🔍 Last segment: '{last_text[:50]}...' | Sentence boundary: {has_boundary}", flush=True)
                    if not has_boundary:
                        # Wait a bit more if we're in the middle of a sentence
                        print(f"[Task Extraction] ⏸️  Waiting for sentence completion...", flush=True)
                        await asyncio.sleep(2)
                        continue
                
                print(f"[Task Extraction] 🔄 Calling Gemini API to extract tasks...", flush=True)
                # Extract tasks using Gemini
                result = await llm_service.extract_tasks(
                    transcript=transcript,
                    existing_tasks=existing_tasks
                )
                
                print(f"[Task Extraction] 📥 Gemini API response - Success: {result.get('success')}, Tasks found: {result.get('count', 0)}", flush=True)
                if not result.get("success"):
                    error = result.get("error", "Unknown error")
                    print(f"[Task Extraction] ❌ Gemini API error: {error}", flush=True)
                    if "raw_response" in result:
                        print(f"[Task Extraction] 📄 Raw response: {result['raw_response'][:200]}...", flush=True)
                
                if result["success"] and result["tasks"]:
                    print(f"[Task Extraction] ✅ Processing {len(result['tasks'])} extracted tasks...", flush=True)
                    # Import Task model and db helpers
                    from models.database import Task, SessionLocal
                    from utils.db_helpers import save_meeting_to_db
                    
                    # Add new tasks to both Task table and meetings.tasks
                    new_task_ids = []
                    for idx, task in enumerate(result["tasks"]):
                        print(f"[Task Extraction] 📝 Task {idx+1}: title='{task.get('title', 'N/A')}', description='{task.get('description', 'N/A')[:50]}...'", flush=True)
                        task_id = str(uuid.uuid4())
                        title = task.get("title", "Untitled Task")
                        description = task.get("description", "")
                        assignee = task.get("assignee")
                        due_date_str = task.get("due_date")
                        priority = task.get("priority", "medium")
                        
                        # Parse due_date if provided
                        due_date = None
                        if due_date_str:
                            try:
                                from dateutil import parser
                                due_date = parser.parse(due_date_str)
                            except Exception:
                                pass  # Keep as None if parsing fails
                        
                        # Save to Task table
                        if SessionLocal:
                            try:
                                db = SessionLocal()
                                db_task = Task(
                                    id=task_id,
                                    meeting_id=meeting_id,
                                    title=title,
                                    description=description,
                                    assignee=assignee,
                                    due_date=due_date,
                                    is_concluded=False,
                                    priority=priority,
                                )
                                db.add(db_task)
                                db.commit()
                                print(f"[Task Extraction] ✅ Saved task to Task table - ID: {task_id}, Title: {title}, Meeting: {meeting_id}", flush=True)
                                db.close()
                            except Exception as e:
                                print(f"[Task Extraction] ❌ Error saving task to database: {e}", flush=True)
                                import traceback
                                traceback.print_exc()
                                if 'db' in locals():
                                    db.rollback()
                                    db.close()
                        else:
                            print(f"[Task Extraction] ⚠️  SessionLocal not available, skipping database save (task will only be in meetings.tasks JSON)", flush=True)
                        
                        # Add task ID to meetings.tasks JSON array
                        task_data = {
                            "task_id": task_id,
                            "title": title,
                            "description": description,
                            "assignee": assignee,
                            "due_date": due_date_str,
                            "is_concluded": False,
                            "priority": priority,
                            "created_at": datetime.now().isoformat(),
                        }
                        meeting["tasks"].append(task_data)
                        new_task_ids.append(task_id)
                        print(f"[Task Extraction] 📋 Added task to meetings.tasks JSON array - task_id: {task_id}", flush=True)
                    
                    # Save updated meeting to database (this updates the meetings.tasks JSON array)
                    print(f"[Task Extraction] 💾 Saving meeting with {len(meeting['tasks'])} total tasks to database...", flush=True)
                    save_meeting_to_db(meeting)
                    print(f"[Task Extraction] ✅ Meeting saved to database", flush=True)
                    
                    # Broadcast update via WebSocket
                    await websocket_manager.send_tasks_update(
                        meeting_id=meeting_id,
                        tasks=meeting["tasks"]
                    )
                    
                    print(f"[Task Extraction] ✅ Extracted {len(new_task_ids)} new tasks for meeting {meeting_id}", flush=True)
                    last_extraction_time = current_time
                elif result["success"] and not result["tasks"]:
                    print(f"[Task Extraction] ℹ️  No new tasks found in transcript", flush=True)
                    last_extraction_time = current_time
            else:
                print(f"[Task Extraction] ⏸️  Not enough transcript segments ({len(transcript)} < 1), skipping extraction", flush=True)
            
            # Wait 15 seconds before next extraction attempt
            await asyncio.sleep(15)
            
        except Exception as e:
            print(f"[Task Extraction] ❌ Error in task extraction task for {meeting_id}: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(15)


async def process_batch_diarization(meeting_id: str):
    """Background task to periodically process audio with speaker diarization"""
    print(f"[Background] [Diarization] 🚀 Starting batch diarization task for meeting {meeting_id}", flush=True)
    while meeting_id in meetings_db and meetings_db[meeting_id]["status"] == "active":
        try:
            # Process batch buffer with diarization (runs every ~1 minute if conditions are met)
            result = await stt_service.process_batch_buffer_with_diarization(
                meeting_id=meeting_id,
                force=False
            )
            
            if result:
                if result.get("success"):
                    segments = result.get("segments", [])
                    if segments:
                        speakers = set(seg.get('speaker', 'Unknown') for seg in segments)
                        print(f"[Background] [Diarization] ✅ Processed {len(segments)} segments, {len(speakers)} speakers: {speakers}", flush=True)
                        
                        # Merge diarized results with existing transcripts (or add as new if no transcripts exist)
                        merge_success = merge_diarized_transcripts(meeting_id, segments)
                        if merge_success:
                            print(f"[Background] [Diarization] ✅ Merged diarized speakers into database for meeting {meeting_id}", flush=True)
                        # Don't log failure as error - it's expected if no transcripts exist yet or no matches found
                else:
                    error = result.get("error", "Unknown error")
                    print(f"[Background] [Diarization] ❌ Batch diarization failed for meeting {meeting_id}: {error}", flush=True)
            # else: result is None, which means conditions weren't met (logged in stt_service)
            
            # Check every 5 seconds for faster response to silence detection
            # The actual processing happens when conditions are met (silence + enough audio)
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"[Background] Error in batch diarization task for {meeting_id}: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(30)

