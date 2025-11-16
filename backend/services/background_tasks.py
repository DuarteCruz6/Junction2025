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

