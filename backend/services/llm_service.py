"""
LLM Service
Handles meeting summarization and task extraction using OpenAI
"""

import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """Service for LLM-powered summarization and task extraction"""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[LLM] ⚠️  WARNING: OPENAI_API_KEY not found in environment variables", flush=True)
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model
        
    async def summarize_meeting(
        self,
        transcript: List[Dict[str, Any]],
        previous_summary: Optional[str] = None,
        incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Generate meeting summary from transcript
        
        Args:
            transcript: List of transcript segments with text, timestamp
            previous_summary: Previous summary for incremental updates
            incremental: If True, generate incremental summary
            
        Returns:
            Dict with summary text and metadata
        """
        try:
            # Check if client is initialized
            if not self.client:
                error_msg = "OpenAI API client not initialized (missing OPENAI_API_KEY)"
                print(f"[LLM] ❌ {error_msg}", flush=True)
                return {
                    "success": False,
                    "error": error_msg,
                    "summary": previous_summary or "Error generating summary",
                }
            
            # Check if transcript is empty
            if not transcript or len(transcript) == 0:
                error_msg = "Empty transcript - cannot generate summary"
                print(f"[LLM] ⚠️  {error_msg}", flush=True)
                return {
                    "success": False,
                    "error": error_msg,
                    "summary": previous_summary or "No transcript available",
                }
            
            # Format transcript for LLM
            transcript_text = self._format_transcript(transcript)
            
            # Build prompt
            if incremental and previous_summary:
                prompt = f"""You are a meeting assistant. Generate a brief updated summary of the meeting based on the new transcript segments.

Previous Summary:
{previous_summary}

New Transcript Segments:
{transcript_text}

Provide a concise, updated summary (1 paragraph, maximum 3-4 sentences) that:
1. Incorporates the new information
2. Maintains context from previous summary
3. Highlights only the most important decisions and action items

Updated Summary:"""
            else:
                prompt = f"""You are a meeting assistant. Generate a brief summary and title for this meeting.

Transcript:
{transcript_text}

Provide:
1. A concise title (maximum 8-10 words) that captures the main topic or purpose of the meeting
2. A concise summary (1 paragraph, maximum 3-4 sentences) that:
   - Captures the main topics discussed
   - Highlights key decisions made
   - Identifies important action items

Format your response as:
Title: [meeting title here]
Summary: [meeting summary here]"""
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional meeting assistant that creates brief, concise summaries and titles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=250,  # Slightly increased to accommodate title
            )
            
            response_text = response.choices[0].message.content
            
            # Parse title and summary from response
            title = None
            summary_text = response_text
            
            if incremental and previous_summary:
                # For incremental updates, we don't generate a new title
                # Just extract the summary
                summary_text = response_text
            else:
                # For new summaries, extract both title and summary
                if "Title:" in response_text and "Summary:" in response_text:
                    parts = response_text.split("Summary:", 1)
                    if len(parts) == 2:
                        title_part = parts[0].replace("Title:", "").strip()
                        summary_text = parts[1].strip()
                        # Clean up title (remove any extra formatting)
                        title = title_part.split("\n")[0].strip()
                        if title.startswith('"') and title.endswith('"'):
                            title = title[1:-1]
                        if title.startswith("'") and title.endswith("'"):
                            title = title[1:-1]
                elif "Title:" in response_text:
                    # Try to extract title even if format is slightly different
                    lines = response_text.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip().startswith("Title:"):
                            title = line.replace("Title:", "").strip()
                            # Get summary from remaining lines
                            summary_text = "\n".join(lines[i+1:]).strip()
                            break
                # If no title found, generate a default one from summary
                if not title:
                    # Fallback: use first few words of summary as title
                    words = summary_text.split()[:8]
                    title = " ".join(words)
                    if len(summary_text.split()) > 8:
                        title += "..."
            
            return {
                "success": True,
                "title": title,
                "summary": summary_text,
                "model": self.model,
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"[LLM] ❌ Error generating summary: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": error_msg,
                "title": None,
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
        try:
            # Format transcript
            transcript_text = self._format_transcript(transcript)
            
            # Format existing tasks if any
            existing_tasks_text = ""
            if existing_tasks:
                existing_tasks_text = "\n\nExisting Tasks:\n"
                for task in existing_tasks:
                    existing_tasks_text += f"- {task.get('description', '')}\n"
            
            # Build prompt
            prompt = f"""You are a meeting assistant. Extract action items and tasks from this meeting transcript.

Transcript:
{transcript_text}
{existing_tasks_text}

Extract all action items, tasks, and commitments mentioned in the meeting. For each task, identify:
1. The task description (required)
2. A brief title for the task (if not clear, derive from description)
3. Who is responsible/assignee (if mentioned, otherwise null)
4. Any deadline or due date (if mentioned, otherwise null)
5. Priority level (high/medium/low based on urgency and importance)

Return ONLY a JSON object with a 'tasks' array in this format:
{{
  "tasks": [
    {{
      "title": "Task title or short description",
      "description": "Full task description",
      "assignee": "Person name or null",
      "due_date": "Date string in ISO format (YYYY-MM-DD) or null",
      "priority": "high/medium/low"
    }}
  ]
}}

Important:
- Return only valid JSON object with a 'tasks' key containing an array
- If no new tasks are found, return {{"tasks": []}}
- Be thorough but avoid duplicates
- Extract implicit tasks (e.g., "we should follow up" becomes a task)
- Set priority based on urgency indicators (deadlines, urgency words, importance)

JSON:"""
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a task extraction assistant. Always return valid JSON with a 'tasks' array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Very low temperature for structured output
                response_format={"type": "json_object"},  # Force JSON response (must be object, not array)
            )
            
            import json
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```", "").strip()
                
                tasks_data = json.loads(response_text)
                
                # Handle both {"tasks": [...]} and [...] formats
                if isinstance(tasks_data, dict) and "tasks" in tasks_data:
                    tasks = tasks_data["tasks"]
                elif isinstance(tasks_data, list):
                    tasks = tasks_data
                else:
                    tasks = []
                
                # Validate and clean tasks
                validated_tasks = []
                for task in tasks:
                    # Ensure required fields
                    if not task.get("description"):
                        continue  # Skip tasks without description
                    
                    validated_task = {
                        "title": task.get("title") or task.get("description", "")[:50],  # Use description as fallback
                        "description": task.get("description", ""),
                        "assignee": task.get("assignee") if task.get("assignee") else None,
                        "due_date": task.get("due_date") if task.get("due_date") else None,
                        "priority": task.get("priority", "medium").lower(),
                    }
                    
                    # Validate priority
                    if validated_task["priority"] not in ["high", "medium", "low"]:
                        validated_task["priority"] = "medium"
                    
                    validated_tasks.append(validated_task)
                
                # Filter out duplicates if existing_tasks provided
                if existing_tasks:
                    existing_descriptions = {t.get("description", "").lower() for t in existing_tasks}
                    validated_tasks = [t for t in validated_tasks if t.get("description", "").lower() not in existing_descriptions]
                
                print(f"[LLM] [OpenAI] ✅ Extracted {len(validated_tasks)} tasks", flush=True)
                
                return {
                    "success": True,
                    "tasks": validated_tasks,
                    "count": len(validated_tasks),
                }
                
            except json.JSONDecodeError:
                # Fallback: try to extract tasks from text
                return {
                    "success": False,
                    "error": "Failed to parse JSON response",
                    "tasks": [],
                    "raw_response": response_text,
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tasks": [],
            }
    
    async def extract_reminders(
        self,
        transcript: List[Dict[str, Any]],
        existing_reminders: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Extract reminders from family call transcript (for elderly care)
        
        Args:
            transcript: List of transcript segments
            existing_reminders: Previously extracted reminders to avoid duplicates
            
        Returns:
            Dict with extracted reminders
        """
        try:
            # Format transcript
            transcript_text = self._format_transcript(transcript)
            
            # Format existing reminders if any
            existing_reminders_text = ""
            if existing_reminders:
                existing_reminders_text = "\n\nExisting Reminders:\n"
                for reminder in existing_reminders:
                    existing_reminders_text += f"- {reminder.get('description', '')}\n"
            
            # Build prompt for reminder extraction
            prompt = f"""You are an assistant helping elderly people remember important things from family calls. Extract reminders, appointments, and things to remember from this conversation.

Transcript:
{transcript_text}
{existing_reminders_text}

Extract all reminders, appointments, and things to remember mentioned in the conversation. For each reminder, identify:
1. The reminder description (required) - what they need to remember
2. A brief title for the reminder (if not clear, derive from description)
3. When to be reminded - date and/or time if mentioned (otherwise null)
4. Whether it's recurring (daily, weekly, monthly, etc.) - if mentioned
5. Priority level (high/medium/low based on importance)

Examples of reminders:
- "Call the doctor tomorrow at 2pm" → reminder_date: tomorrow, reminder_time: "14:00", priority: high
- "Take medication every morning" → is_recurring: true, recurrence_pattern: "daily", priority: high
- "Visit mom next week" → reminder_date: next week, priority: medium
- "Don't forget the appointment on Friday" → reminder_date: Friday, priority: high

Return ONLY a JSON object with a 'reminders' array in this format:
{{
  "reminders": [
    {{
      "title": "Reminder title or short description",
      "description": "Full reminder description",
      "reminder_date": "Date string in ISO format (YYYY-MM-DD) or null",
      "reminder_time": "Time string in HH:MM format (24-hour) or null",
      "is_recurring": true/false,
      "recurrence_pattern": "daily/weekly/monthly or null",
      "priority": "high/medium/low"
    }}
  ]
}}

Important:
- Return only valid JSON object with a 'reminders' key containing an array
- If no reminders are found, return {{"reminders": []}}
- Be thorough but avoid duplicates
- Extract implicit reminders (e.g., "we should do this later" becomes a reminder)
- Set priority based on importance (medical appointments = high, casual mentions = low)
- For dates, try to infer from context (today, tomorrow, next week, specific dates)

JSON:"""
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a reminder extraction assistant for elderly care. Always return valid JSON with a 'reminders' array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Very low temperature for structured output
                response_format={"type": "json_object"},  # Force JSON response
            )
            
            import json
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```", "").strip()
                
                reminders_data = json.loads(response_text)
                
                # Handle both {"reminders": [...]} and [...] formats
                if isinstance(reminders_data, dict) and "reminders" in reminders_data:
                    reminders = reminders_data["reminders"]
                elif isinstance(reminders_data, list):
                    reminders = reminders_data
                else:
                    reminders = []
                
                # Validate and clean reminders
                validated_reminders = []
                for reminder in reminders:
                    # Ensure required fields
                    if not reminder.get("description"):
                        continue  # Skip reminders without description
                    
                    validated_reminder = {
                        "title": reminder.get("title") or reminder.get("description", "")[:50],
                        "description": reminder.get("description", ""),
                        "reminder_date": reminder.get("reminder_date") if reminder.get("reminder_date") else None,
                        "reminder_time": reminder.get("reminder_time") if reminder.get("reminder_time") else None,
                        "is_recurring": reminder.get("is_recurring", False),
                        "recurrence_pattern": reminder.get("recurrence_pattern") if reminder.get("recurrence_pattern") else None,
                        "priority": reminder.get("priority", "medium").lower(),
                    }
                    
                    # Validate priority
                    if validated_reminder["priority"] not in ["high", "medium", "low"]:
                        validated_reminder["priority"] = "medium"
                    
                    # Validate recurrence pattern
                    if validated_reminder["is_recurring"] and validated_reminder["recurrence_pattern"]:
                        if validated_reminder["recurrence_pattern"] not in ["daily", "weekly", "monthly"]:
                            validated_reminder["recurrence_pattern"] = None
                    
                    validated_reminders.append(validated_reminder)
                
                # Filter out duplicates if existing_reminders provided
                if existing_reminders:
                    existing_descriptions = {r.get("description", "").lower() for r in existing_reminders}
                    validated_reminders = [r for r in validated_reminders if r.get("description", "").lower() not in existing_descriptions]
                
                print(f"[LLM] [OpenAI] ✅ Extracted {len(validated_reminders)} reminders", flush=True)
                
                return {
                    "success": True,
                    "reminders": validated_reminders,
                    "count": len(validated_reminders),
                }
                
            except json.JSONDecodeError:
                # Fallback: try to extract reminders from text
                return {
                    "success": False,
                    "error": "Failed to parse JSON response",
                    "reminders": [],
                    "raw_response": response_text,
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "reminders": [],
            }
    
    def _format_transcript(self, transcript: List[Dict[str, Any]]) -> str:
        """Format transcript segments into readable text (without speaker information)"""
        formatted = []
        for segment in transcript:
            text = segment.get("text", "")
            timestamp = segment.get("start", 0)
            
            # Format: [00:05] Text (no speaker information)
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            formatted.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        
        return "\n".join(formatted)


# Singleton instance
llm_service = LLMService()

