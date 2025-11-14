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
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional meeting assistant that creates clear, concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=500,
            )
            
            summary_text = response.choices[0].message.content
            
            return {
                "success": True,
                "summary": summary_text,
                "model": self.model,
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
1. The task description
2. Who is responsible (if mentioned)
3. Any deadline or due date (if mentioned)

Return ONLY a JSON array of tasks in this format:
[
  {{
    "description": "Task description",
    "assignee": "Person name or null",
    "due_date": "Date string or null",
    "priority": "high/medium/low"
  }}
]

If no new tasks are found, return an empty array [].

JSON:"""
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a task extraction assistant. Always return valid JSON arrays."},
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
                
                tasks_data = json.loads(response_text)
                
                # Handle both {"tasks": [...]} and [...] formats
                if isinstance(tasks_data, dict) and "tasks" in tasks_data:
                    tasks = tasks_data["tasks"]
                elif isinstance(tasks_data, list):
                    tasks = tasks_data
                else:
                    tasks = []
                
                # Filter out duplicates if existing_tasks provided
                if existing_tasks:
                    existing_descriptions = {t.get("description", "").lower() for t in existing_tasks}
                    tasks = [t for t in tasks if t.get("description", "").lower() not in existing_descriptions]
                
                return {
                    "success": True,
                    "tasks": tasks,
                    "count": len(tasks),
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

