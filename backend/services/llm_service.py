"""
LLM Service
Handles meeting summarization and task extraction using Google Gemini
"""

import os
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """Service for LLM-powered summarization and task extraction"""
    
    def __init__(self, model: str = None):
        # Get model from environment variable or use default
        # Use gemini-2.5-flash as default (fast and available)
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        print(f"[LLM Service] 🔧 Initializing LLM Service with model: {model}", flush=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            error_msg = "GEMINI_API_KEY not found in environment variables"
            print(f"[LLM Service] ❌ {error_msg}", flush=True)
            raise ValueError(error_msg)
        print(f"[LLM Service] ✅ GEMINI_API_KEY found (length: {len(api_key)} characters)", flush=True)
        genai.configure(api_key=api_key)
        
        # Try to list available models first to see what's available
        try:
            print(f"[LLM Service] 🔍 Listing available Gemini models...", flush=True)
            available_models = genai.list_models()
            model_names = [m.name for m in available_models if 'generateContent' in m.supported_generation_methods]
            print(f"[LLM Service] 📋 Available models with generateContent: {model_names[:5]}...", flush=True)
        except Exception as e:
            print(f"[LLM Service] ⚠️  Could not list models: {e}", flush=True)
            model_names = []
        
        # Try to initialize the requested model
        try:
            self.model = genai.GenerativeModel(model)
            self.model_name = model
            print(f"[LLM Service] ✅ LLM Service initialized successfully with model: {model}", flush=True)
        except Exception as e:
            print(f"[LLM Service] ❌ Failed to initialize model {model}: {e}", flush=True)
            # Try fallback models in order (using known available models)
            fallback_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-pro-latest"]
            if model_names:
                # Use available models if we could list them (extract short names)
                available_short_names = [m.split('/')[-1] for m in model_names if m.split('/')[-1] not in [model]]
                # Prefer stable models over previews
                stable_models = [m for m in available_short_names if 'preview' not in m.lower() and 'exp' not in m.lower()]
                fallback_models = stable_models[:3] + fallback_models
            
            for fallback_model in fallback_models:
                if fallback_model == model:
                    continue
                print(f"[LLM Service] 🔄 Trying fallback model: {fallback_model}", flush=True)
                try:
                    self.model = genai.GenerativeModel(fallback_model)
                    self.model_name = fallback_model
                    print(f"[LLM Service] ✅ LLM Service initialized with fallback model: {fallback_model}", flush=True)
                    break
                except Exception as e2:
                    print(f"[LLM Service] ⚠️  Model {fallback_model} also failed: {e2}", flush=True)
                    continue
            else:
                # If we exhausted all fallbacks
                raise ValueError(f"Failed to initialize any Gemini model. Tried: {model} and fallbacks: {fallback_models}")
        
    async def summarize_meeting(
        self,
        transcript: List[Dict[str, Any]],
        previous_summary: Optional[str] = None,
        incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Generate meeting summary from transcript
        
        Args:
            transcript: List of transcript segments with speaker, text, timestamp
            previous_summary: Previous summary for incremental updates
            incremental: If True, generate incremental summary
            
        Returns:
            Dict with summary text and metadata
        """
        try:
            # Format transcript for LLM
            transcript_text = self._format_transcript(transcript)
            
            # Build prompt
            if incremental and previous_summary:
                prompt = f"""You are a meeting assistant. Generate an updated summary of the meeting based on the new transcript segments.

Previous Summary:
{previous_summary}

New Transcript Segments:
{transcript_text}

Provide a comprehensive, updated summary that:
1. Incorporates the new information
2. Maintains context from previous summary
3. Highlights key decisions, action items, and important points
4. Is concise but complete (2-3 paragraphs)

Updated Summary:"""
            else:
                prompt = f"""You are a meeting assistant. Generate a comprehensive summary of this meeting.

Transcript:
{transcript_text}

Provide a summary that:
1. Captures the main topics discussed
2. Highlights key decisions made
3. Identifies important action items
4. Notes any deadlines or commitments
5. Is well-structured and easy to read (2-3 paragraphs)

Summary:"""
            
            # Call Gemini (run in executor since it's synchronous)
            import asyncio
            loop = asyncio.get_event_loop()
            
            def generate_summary():
                full_prompt = f"You are a professional meeting assistant that creates clear, concise summaries.\n\n{prompt}"
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,  # Lower temperature for more consistent summaries
                        max_output_tokens=500,
                    )
                )
                return response.text
            
            summary_text = await loop.run_in_executor(None, generate_summary)
            
            return {
                "success": True,
                "summary": summary_text,
                "model": self.model_name,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary": previous_summary or "Error generating summary",
            }
    
    async def extract_tasks(
        self,
        transcript: List[Dict[str, Any]],
        existing_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Extract tasks from meeting transcript
        
        Args:
            transcript: List of transcript segments
            existing_tasks: Previously extracted tasks to avoid duplicates
            
        Returns:
            Dict with extracted tasks
        """
        print(f"[LLM Service] 🔍 Starting task extraction - Transcript segments: {len(transcript)}, Existing tasks: {len(existing_tasks) if existing_tasks else 0}", flush=True)
        try:
            # Format transcript
            transcript_text = self._format_transcript(transcript)
            print(f"[LLM Service] 📄 Formatted transcript length: {len(transcript_text)} characters", flush=True)
            if len(transcript_text) > 500:
                print(f"[LLM Service] 📄 Transcript preview: {transcript_text[:200]}...", flush=True)
            else:
                print(f"[LLM Service] 📄 Full transcript: {transcript_text}", flush=True)
            
            # Format existing tasks if any
            existing_tasks_text = ""
            if existing_tasks:
                existing_tasks_text = "\n\nExisting Tasks:\n"
                for task in existing_tasks:
                    task_id = task.get('task_id') or task.get('id', '')
                    title = task.get('title', '')
                    description = task.get('description', '')
                    existing_tasks_text += f"- [{task_id}] {title}: {description}\n"
                print(f"[LLM Service] 📋 Existing tasks: {existing_tasks_text[:200]}...", flush=True)
            
            # Build prompt
            prompt = f"""You are a meeting assistant. Extract action items and tasks from this meeting transcript.

Transcript:
{transcript_text}
{existing_tasks_text}

Extract all action items, tasks, and commitments mentioned in the meeting. For each task, identify:
1. A concise task title (short, 3-8 words)
2. A detailed task description
3. Who is responsible (if mentioned)
4. Any deadline or due date (if mentioned)
5. Priority level (high/medium/low)

Return ONLY a JSON array of tasks in this format:
[
  {{
    "title": "Short task title",
    "description": "Detailed task description",
    "assignee": "Person name or null",
    "due_date": "Date string or null",
    "priority": "high/medium/low"
  }}
]

If no new tasks are found, return an empty array [].

Important: Only extract NEW tasks that are not already in the existing tasks list above.

JSON:"""
            
            # Call Gemini (run in executor since it's synchronous)
            import json
            import asyncio
            loop = asyncio.get_event_loop()
            
            print(f"[LLM Service] 🤖 Calling Gemini API (model: {self.model_name})...", flush=True)
            print(f"[LLM Service] 📤 Prompt length: {len(prompt)} characters", flush=True)
            
            def extract_tasks_sync():
                full_prompt = f"You are a task extraction assistant. Always return valid JSON arrays.\n\n{prompt}"
                last_error = None
                
                # Try the current model first
                models_to_try = [self.model_name]
                # Add alternative model names to try (using available models from the API)
                alternative_models = [
                    "gemini-2.5-flash",      # Fast and efficient
                    "gemini-2.5-pro",       # Better quality
                    "gemini-2.0-flash",     # Alternative flash model
                    "gemini-pro-latest",    # Latest pro model
                    "gemini-flash-latest",  # Latest flash model
                ]
                for alt in alternative_models:
                    if alt not in models_to_try:
                        models_to_try.append(alt)
                
                for model_name in models_to_try:
                    try:
                        print(f"[LLM Service] 🤖 Trying model: {model_name}", flush=True)
                        # Create a new model instance for this attempt
                        model_obj = genai.GenerativeModel(model_name)
                        response = model_obj.generate_content(
                            full_prompt,
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.2,  # Very low temperature for structured output
                                response_mime_type="application/json",  # Force JSON response
                            )
                        )
                        # If successful, update the instance model for future calls
                        if model_name != self.model_name:
                            self.model = model_obj
                            self.model_name = model_name
                            print(f"[LLM Service] ✅ Successfully using model: {model_name}", flush=True)
                        return response.text
                    except Exception as e:
                        error_str = str(e)
                        last_error = e
                        print(f"[LLM Service] ⚠️  Model {model_name} failed: {error_str[:200]}", flush=True)
                        # Continue to next model
                        continue
                
                # If all models failed, raise the last error
                print(f"[LLM Service] ❌ All models failed. Last error: {last_error}", flush=True)
                raise last_error
            
            response_text = await loop.run_in_executor(None, extract_tasks_sync)
            print(f"[LLM Service] 📥 Received response from Gemini: {len(response_text)} characters", flush=True)
            print(f"[LLM Service] 📥 Response preview: {response_text[:300]}...", flush=True)
            
            # Parse JSON response
            try:
                print(f"[LLM Service] 🔧 Parsing JSON response...", flush=True)
                # Try to extract JSON from response
                original_response = response_text
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                    print(f"[LLM Service] 🔧 Removed markdown code block markers", flush=True)
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```", "").strip()
                    print(f"[LLM Service] 🔧 Removed code block markers", flush=True)
                
                tasks_data = json.loads(response_text)
                print(f"[LLM Service] ✅ JSON parsed successfully. Type: {type(tasks_data)}", flush=True)
                
                # Handle both {"tasks": [...]} and [...] formats
                if isinstance(tasks_data, dict) and "tasks" in tasks_data:
                    tasks = tasks_data["tasks"]
                    print(f"[LLM Service] 📋 Found tasks in dict format: {len(tasks)} tasks", flush=True)
                elif isinstance(tasks_data, list):
                    tasks = tasks_data
                    print(f"[LLM Service] 📋 Found tasks in list format: {len(tasks)} tasks", flush=True)
                else:
                    tasks = []
                    print(f"[LLM Service] ⚠️  Unexpected format, no tasks found", flush=True)
                
                # Filter out duplicates if existing_tasks provided
                if existing_tasks:
                    # Check both title and description for duplicates
                    existing_titles = {t.get("title", "").lower() for t in existing_tasks if t.get("title")}
                    existing_descriptions = {t.get("description", "").lower() for t in existing_tasks if t.get("description")}
                    initial_count = len(tasks)
                    tasks = [
                        t for t in tasks 
                        if t.get("title", "").lower() not in existing_titles 
                        and t.get("description", "").lower() not in existing_descriptions
                    ]
                    filtered_count = initial_count - len(tasks)
                    if filtered_count > 0:
                        print(f"[LLM Service] 🔍 Filtered out {filtered_count} duplicate tasks", flush=True)
                
                print(f"[LLM Service] ✅ Returning {len(tasks)} unique tasks", flush=True)
                return {
                    "success": True,
                    "tasks": tasks,
                    "count": len(tasks),
                }
                
            except json.JSONDecodeError as e:
                # Fallback: try to extract tasks from text
                print(f"[LLM Service] ❌ JSON parsing failed: {e}", flush=True)
                print(f"[LLM Service] 📄 Full response that failed to parse: {response_text}", flush=True)
                return {
                    "success": False,
                    "error": f"Failed to parse JSON response: {str(e)}",
                    "tasks": [],
                    "raw_response": response_text,
                }
                
        except Exception as e:
            print(f"[LLM Service] ❌ Exception in extract_tasks: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "tasks": [],
            }
    
    def _format_transcript(self, transcript: List[Dict[str, Any]]) -> str:
        """Format transcript segments into readable text"""
        formatted = []
        for segment in transcript:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            timestamp = segment.get("start", 0)
            
            # Format: [00:05] Speaker: Text
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            formatted.append(f"[{minutes:02d}:{seconds:02d}] {speaker}: {text}")
        
        return "\n".join(formatted)


# Singleton instance
llm_service = LLMService()

