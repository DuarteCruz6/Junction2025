"""
WebSocket endpoints for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import json
import base64
import sys
from datetime import datetime
from typing import Optional

from services.websocket_manager import websocket_manager
from services.stt_service import stt_service
from utils.db_helpers import get_meeting_from_db_or_memory, save_meeting_to_db
from models.database import UserSettings, SessionLocal

router = APIRouter()


@router.websocket("/ws/meetings/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket, meeting_id)
    
    try:
        # Send initial state
        meeting = get_meeting_from_db_or_memory(meeting_id)
        if meeting:
            await websocket_manager.send_personal_message({
                "type": "initial_state",
                "data": {
                    "meeting_id": meeting_id,
                    "status": meeting["status"],
                    "summary": meeting.get("summary"),
                    "tasks": meeting.get("tasks", []),
                    "transcript_count": len(meeting.get("transcript", [])),
                }
            }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming messages if needed
                # For now, just keep connection alive
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        print(f"WebSocket error for meeting {meeting_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, meeting_id)


@router.websocket("/ws/audio/{meeting_id}")
async def audio_streaming_endpoint(
    websocket: WebSocket, 
    meeting_id: str,
    user_id: Optional[str] = Query(None, description="User ID for language preferences")
):
    """WebSocket endpoint for streaming audio chunks and receiving transcriptions"""
    await websocket.accept()
    
    # Verify meeting exists
    meeting = get_meeting_from_db_or_memory(meeting_id)
    if not meeting:
        print(f"[WebSocket] ❌ Meeting {meeting_id} not found, closing connection")
        await websocket.close(code=1008, reason="Meeting not found")
        return
    
    # Get user's language preference if user_id is provided
    language_preference = None
    if user_id and SessionLocal:
        try:
            db = SessionLocal()
            user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if user_settings and user_settings.preferred_language:
                language_preference = user_settings.preferred_language
                print(f"[WebSocket] 🌐 Using user's preferred language: {language_preference}")
            db.close()
        except Exception as e:
            print(f"[WebSocket] ⚠️  Could not retrieve user settings: {e}")
            # Continue with auto-detect if settings retrieval fails
    
    # Try to connect to realtime API if enabled
    use_realtime = stt_service.use_realtime
    realtime_connected = False
    
    if use_realtime:
        # Callback for partial transcripts (interim results)
        async def on_partial_transcript(data: dict):
            """Handle partial transcript from realtime API"""
            try:
                text = data.get("text", "")
                if text:
                    await websocket.send_json({
                        "type": "partial_transcript",
                        "data": {
                            "text": text,
                            "meeting_id": meeting_id
                        }
                    })
            except Exception as e:
                print(f"[WebSocket] Error sending partial transcript: {e}")
        
        # Callback for committed transcripts (final results)
        async def on_committed_transcript(data: dict):
            """Handle committed transcript from realtime API"""
            try:
                # Handle errors
                if data.get("type") == "error":
                    error_msg = data.get("error", "Unknown error")
                    print(f"[WebSocket] ❌ Realtime API error: {error_msg}")
                    try:
                        await websocket.send_json({
                            "type": "transcription_error",
                            "data": {"error": error_msg}
                        })
                    except Exception:
                        pass
                    # Don't fall back immediately - let it try to reconnect
                    return
                
                text = data.get("text", "")
                words = data.get("words", [])
                
                if not text:
                    return
                
                meeting = get_meeting_from_db_or_memory(meeting_id)
                if not meeting:
                    return
                
                # Check for duplicates: if the last transcript entry has the same text, skip it
                transcript = meeting.get("transcript", [])
                if transcript:
                    last_entry = transcript[-1]
                    if last_entry.get("text") == text and last_entry.get("speaker") == "Unknown":
                        # Duplicate detected, skip
                        return
                
                # Calculate timing from words if available
                start_time = 0.0
                end_time = 0.0
                if words and len(words) > 0:
                    start_time = words[0].get("start", 0.0) if isinstance(words[0], dict) else 0.0
                    end_time = words[-1].get("end", 0.0) if isinstance(words[-1], dict) else 0.0
                
                transcript_entry = {
                    "text": text,
                    "speaker": "Unknown",  # Realtime API doesn't support diarization
                    "start": start_time,
                    "end": end_time,
                    "timestamp": datetime.now().isoformat(),
                }
                
                print(f"📝 Unknown: {text}", flush=True)
                
                meeting["transcript"].append(transcript_entry)
                save_meeting_to_db(meeting)
                
                # Mark that a committed transcript was received (for detecting natural pauses in batch processing)
                stt_service.mark_committed_transcript(meeting_id)
                
                # Broadcast to all WebSocket connections
                try:
                    await websocket_manager.send_transcript_update(
                        meeting_id=meeting_id,
                        transcript_entry=transcript_entry
                    )
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting transcript: {e}")
                
                # Send to audio streaming client
                await websocket.send_json({
                    "type": "transcription_result",
                    "data": {
                        "segments": [transcript_entry],
                        "full_text": text,
                        "count": 1
                    }
                })
            except Exception as e:
                print(f"[WebSocket] Error handling committed transcript: {e}")
        
        # Connect to realtime API
        realtime_connected = await stt_service.connect_realtime(
            meeting_id=meeting_id,
            on_partial_transcript=on_partial_transcript,
            on_committed_transcript=on_committed_transcript,
            language=None  # Auto-detect
        )
        
        if not realtime_connected:
            use_realtime = False
    
    # Callback function to send transcript updates (for batch API fallback)
    async def send_transcript_callback(result: dict, meeting_id: str):
        """Callback to send transcription results via WebSocket and broadcast"""
        try:
            # print(f"[WebSocket] Callback called for meeting {meeting_id}, success={result.get('success')}")  # DEBUG
            
            # Check if WebSocket is still open (try-except for safety)
            try:
                # Try to check connection state
                if hasattr(websocket, 'client_state'):
                    state = websocket.client_state
                    if hasattr(state, 'name') and state.name != "CONNECTED":
                        # print(f"[WebSocket] Connection closed, cannot send transcription")  # DEBUG
                        return
            except Exception:
                # If we can't check state, try to send anyway (will fail gracefully)
                pass
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                print(f"[WebSocket] Transcription error: {error_msg}")  # Keep error messages
                try:
                    # Check if WebSocket is still connected before sending
                    await websocket.send_json({
                        "type": "transcription_error",
                        "data": {"error": error_msg}
                    })
                except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                    # WebSocket closed or error sending, ignore silently
                    print(f"[WebSocket] Connection closed, cannot send error: {type(e).__name__}")
                    return
                except Exception as e:
                    # Other errors, log but don't crash
                    print(f"[WebSocket] Error sending error message: {e}")
                    return
                return
            
            meeting = get_meeting_from_db_or_memory(meeting_id)
            if not meeting:
                # print(f"[WebSocket] Meeting {meeting_id} not found")  # DEBUG
                return
            
            segments = result.get("segments", [])
            # print(f"[WebSocket] Processing {len(segments)} segments")  # DEBUG
            
            # if not segments:
            #     print(f"[WebSocket] No segments in result, full_text: {result.get('full_text', '')[:100]}")  # DEBUG
            
            # Process each segment
            new_segments = []
            for segment in segments:
                transcript_entry = {
                    "text": segment["text"],
                    "speaker": segment["speaker"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Show transcription (clean output)
                speaker = segment.get("speaker", "Unknown")
                text = segment.get("text", "")
                print(f"📝 {speaker}: {text}", flush=True)
                
                meeting["transcript"].append(transcript_entry)
                new_segments.append(transcript_entry)
                
                # Broadcast to all WebSocket connections for this meeting
                try:
                    await websocket_manager.send_transcript_update(
                        meeting_id=meeting_id,
                        transcript_entry=transcript_entry
                    )
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting transcript: {e}")  # Keep error messages
            
            # Save updated meeting
            save_meeting_to_db(meeting)
            
            # Send confirmation to audio streaming client
            response_data = {
                "type": "transcription_result",
                "data": {
                    "segments": new_segments,
                    "full_text": result.get("full_text", ""),
                    "count": len(new_segments)
                }
            }
            # print(f"[WebSocket] Sending transcription_result with {len(new_segments)} segments")  # DEBUG
            try:
                await websocket.send_json(response_data)
                # print(f"[WebSocket] Transcription result sent successfully")  # DEBUG
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as ws_error:
                # WebSocket is closed or disconnected, ignore silently
                print(f"[WebSocket] Connection closed, cannot send transcription result: {type(ws_error).__name__}")
                return
            except Exception as ws_error:
                # Other WebSocket errors
                print(f"[WebSocket] Error sending transcription result: {ws_error}")
                return
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            # WebSocket disconnected, ignore silently
            print(f"[WebSocket] Connection closed in callback: {type(e).__name__}")
        except Exception as e:
            print(f"[WebSocket] Error in callback: {e}")  # Keep error messages
            import traceback
            traceback.print_exc()
            # Don't try to send error message if WebSocket is closed
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "data": {
                "meeting_id": meeting_id,
                "status": "ready",
                "message": "Audio streaming ready"
            }
        })
        
        while True:
            try:
                # Receive audio data (can be text with base64 or binary)
                try:
                    message = await websocket.receive()
                except RuntimeError as e:
                    # WebSocket disconnected
                    if "disconnect" in str(e).lower() or "receive" in str(e).lower():
                        print(f"[WebSocket] ❌ Connection closed: {e}")
                        break
                    raise
                
                audio_chunk = None
                is_final = False
                
                if "bytes" in message:
                    # Binary audio data (PCM)
                    audio_chunk = message["bytes"]
                    is_final = False
                elif "text" in message:
                    # JSON message with audio data or control
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "audio_chunk":
                            # Base64 encoded audio
                            audio_chunk = base64.b64decode(data["data"])
                            is_final = data.get("is_final", False)
                        elif data.get("type") == "end_stream":
                            # Final chunk - commit realtime transcript and wait for final results
                            print(f"[WebSocket] 📤 Received end_stream for meeting {meeting_id}, committing realtime transcript...")
                            if use_realtime and realtime_connected:
                                try:
                                    # Commit any pending realtime transcript
                                    await stt_service.commit_realtime_transcript(meeting_id)
                                    print(f"[WebSocket] ✅ Committed realtime transcript for meeting {meeting_id}")
                                    
                                    # Wait a bit for the final committed transcript to arrive
                                    import asyncio
                                    await asyncio.sleep(1.5)  # Wait 1.5 seconds for final transcript
                                    print(f"[WebSocket] ⏳ Waited for final realtime transcript...")
                                except Exception as e:
                                    print(f"[WebSocket] ⚠️  Error committing realtime transcript: {e}")
                            
                            is_final = True
                            audio_chunk = b""
                        elif data.get("type") == "ping":
                            # Keep-alive ping
                            await websocket.send_json({"type": "pong"})
                            continue
                        else:
                            continue
                    except json.JSONDecodeError:
                        continue
                else:
                    continue
                
                if audio_chunk:
                    print(f"[WebSocket] 📥 Received audio chunk: {len(audio_chunk)} bytes", flush=True)
                    # DISABLED: Add to batch processing buffer (diarization on stand-by)
                    # Keeping buffer adding for later when diarization is re-enabled
                    # This runs in parallel with realtime transcription
                    # await stt_service.add_audio_to_batch_buffer(audio_chunk, meeting_id)
                    
                    # Use realtime API if connected, otherwise use batch API
                    if use_realtime and realtime_connected:
                        # Send directly to realtime API (no buffering needed)
                        success = await stt_service.send_audio_to_realtime(
                            meeting_id=meeting_id,
                            audio_chunk=audio_chunk
                        )
                        if success:
                            print(f"[WebSocket] ✅ Sent {len(audio_chunk)} bytes to realtime API", flush=True)
                        else:
                            print(f"[WebSocket] ⚠️  Failed to send to realtime API", flush=True)
                        
                        if not success:
                            # Realtime API failed, try to reconnect once
                            if realtime_connected:
                                # Disconnect and try to reconnect
                                await stt_service.disconnect_realtime(meeting_id)
                                realtime_connected = await stt_service.connect_realtime(
                                    meeting_id=meeting_id,
                                    on_partial_transcript=on_partial_transcript,
                                    on_committed_transcript=on_committed_transcript,
                                    language=None
                                )
                                
                                if realtime_connected:
                                    # Try sending again
                                    success = await stt_service.send_audio_to_realtime(
                                        meeting_id=meeting_id,
                                        audio_chunk=audio_chunk
                                    )
                            
                            if not success:
                                # Reconnection failed, fall back to batch API
                                use_realtime = False
                                realtime_connected = False
                                # Continue to batch API processing below
                            else:
                                # Successfully sent after reconnection
                                try:
                                    await websocket.send_json({
                                        "type": "audio_received",
                                        "data": {
                                            "status": "processing_realtime"
                                        }
                                    })
                                except Exception:
                                    pass
                                continue
                        else:
                            # Successfully sent to realtime API, skip batch processing
                            try:
                                await websocket.send_json({
                                    "type": "audio_received",
                                    "data": {
                                        "status": "processing_realtime"
                                    }
                                })
                            except Exception:
                                pass
                            continue
                    
                    # Batch API processing (fallback or if realtime disabled)
                    async with stt_service.buffer_lock:
                        # Add chunk to buffer
                        stt_service.streaming_buffers[meeting_id].append(audio_chunk)
                        
                        # Calculate buffer duration
                        total_pcm = b''.join(stt_service.streaming_buffers[meeting_id])
                        buffer_duration = stt_service._calculate_audio_duration(
                            total_pcm,
                            stt_service.SAMPLE_RATE,
                            stt_service.SAMPLE_WIDTH
                        )
                        
                        # Check if we should process
                        should_process = (
                            is_final or
                            buffer_duration >= stt_service.MAX_BUFFER_DURATION or
                            buffer_duration >= stt_service.MIN_BUFFER_DURATION
                        )
                        
                        if should_process and len(stt_service.streaming_buffers[meeting_id]) > 0:
                            # Get buffer and clear it
                            buffer_pcm = b''.join(stt_service.streaming_buffers[meeting_id])
                            stt_service.streaming_buffers[meeting_id].clear()
                            
                            # Convert to WAV
                            wav_data = stt_service._pcm_to_wav(
                                buffer_pcm,
                                stt_service.SAMPLE_RATE,
                                stt_service.CHANNELS,
                                stt_service.SAMPLE_WIDTH
                            )
                            
                            # Process with callback
                            import asyncio
                            asyncio.create_task(
                                stt_service._process_buffer(
                                    wav_data,
                                    meeting_id,
                                    is_final,
                                    send_transcript_callback
                                )
                            )
                            
                            # Send acknowledgment (with error handling)
                            try:
                                await websocket.send_json({
                                    "type": "audio_received",
                                    "data": {
                                        "buffer_duration": buffer_duration,
                                        "status": "processing"
                                    }
                                })
                            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                                print(f"[WebSocket] Connection closed while sending acknowledgment: {type(e).__name__}")
                                break
                            except Exception as e:
                                print(f"[WebSocket] Error sending acknowledgment: {e}")
                                # Continue processing even if acknowledgment fails
                
            except WebSocketDisconnect:
                print(f"[WebSocket] Client disconnected for meeting {meeting_id}")
                break
            except RuntimeError as e:
                # Check if it's a disconnection error
                error_str = str(e).lower()
                if "disconnect" in error_str or "connection" in error_str or "closed" in error_str:
                    print(f"[WebSocket] Connection closed: {e}")
                    break
                # Re-raise if it's a different RuntimeError
                raise
            except Exception as e:
                print(f"[WebSocket] Error processing audio chunk for meeting {meeting_id}: {e}")  # Keep error messages
                import traceback
                traceback.print_exc()
                try:
                    # Only send error if WebSocket is still connected
                    await websocket.send_json({
                        "type": "error",
                        "data": {"error": str(e)}
                    })
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    # WebSocket already closed, ignore
                    print(f"[WebSocket] Cannot send error message - connection closed")
                    break
                except Exception as send_error:
                    print(f"[WebSocket] Error sending error message: {send_error}")
                
    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected from audio stream for meeting {meeting_id}")
    except Exception as e:
        print(f"[WebSocket] WebSocket audio streaming error for meeting {meeting_id}: {e}")  # Keep error messages
        import traceback
        traceback.print_exc()
    finally:
        print(f"[WebSocket] Cleaning up audio stream for meeting {meeting_id}")
        # Before disconnecting, commit any final realtime transcripts if not already done
        try:
            if 'realtime_connected' in locals() and realtime_connected:
                # Check if meeting is still active (if it's being stopped, the stop endpoint will handle commit)
                meeting = get_meeting_from_db_or_memory(meeting_id)
                if meeting and meeting.get("status") != "completed":
                    # Meeting is still active, commit before disconnecting
                    print(f"[WebSocket] 🔄 Committing final realtime transcript before disconnect...")
                    await stt_service.commit_realtime_transcript(meeting_id)
                    import asyncio
                    await asyncio.sleep(0.5)  # Brief wait for final transcript
                
                # Now disconnect
                await stt_service.disconnect_realtime(meeting_id)
        except Exception as e:
            print(f"[WebSocket] Error disconnecting realtime API: {e}")
        # Clear buffers on disconnect
        stt_service.clear_buffer(meeting_id)
        stt_service.clear_batch_buffer(meeting_id)
        # Only close if still connected
        try:
            if hasattr(websocket, 'client_state'):
                state = websocket.client_state
                if hasattr(state, 'name') and state.name == "CONNECTED":
                    await websocket.close(code=1000, reason="Stream ended")
            else:
                # Fallback: try to close anyway
                try:
                    await websocket.close(code=1000, reason="Stream ended")
                except Exception:
                    # Already closed, ignore
                    pass
        except Exception as e:
            # Connection already closed, ignore
            print(f"[WebSocket] Connection already closed during cleanup: {type(e).__name__}")

