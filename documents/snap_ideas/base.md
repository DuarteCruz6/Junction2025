# Base Specification Document

## Theme connection – Utopia & Dystopia

This project explores a future where augmented memory and real-time understanding create a utopian boost to productivity and clarity, while exposing the dystopian risks of continuous monitoring, identification, and data capture.

## Core Features (Glasses + Backend)
- Speech-to-Text (STT): Convert all spoken audio into text in real time.
- Live Translation (optional): Translate detected speech into the user’s preferred language.
- Person Detection & Identification: Detect and identify people in the scene (if known), enabling the system to record who said what during meetings or conversations.
- Conversation & Meeting Summaries: Generate summaries of: meetings (multi-person); conversations with a specific identified person
- Task Extraction (To-Do List): Automatically detect action items during meetings; Tasks go to a Standby queue first; The user must accept them later via the mobile app.
- Tasks With Due Dates: When the system detects a deadline or date, it assigns it to the task.
- Document Summarization (optional, extra): The system can summarize uploaded or captured documents.


## Web App
### Frontend Features
- Live Video Feed: Simulates the glasses’ visual perspective.
- Live Meeting Summary (optional): Displays ongoing or periodic summary updates of the meeting.
- Live Translation Display
- Task Creation Notifications: Shows when a task was added to Standby, including any due date.
- Task Notifications: Alerts for tasks due today/this week/overdue tasks/etc
- New Person Warning: Alerts the user that an unidentified person was seen and needs to be registered in the mobile app.
- Person Pop Up: Shows contextual info when a known person appears; ex: This is Anna — last meeting: design review. You promised to send draft.

### Backend Responsibilities
- Speech-to-Text processing
- Person Detection & Identification
- Recording and storing speaker-labeled transcripts
- Adding tasks to Standby with due dates
- Storing conversation and meeting summaries
- Communicating with the Mobile App backend (tasks, people, history)


## Mobile App
### Frontend Features
- Standby Tasks: User can accept or decline extracted tasks.
- Accepted Tasks: Shows all confirmed tasks organized by due date.
- People Directory: List of all known people with: their profile; history of conversations/meetings; summary of each interaction; connection to tasks or mentions
- New Person Identification: Interface to register a new person detected by the system.
- Add tasks that were not detected by the glasses

### Backend Responsibilities
- Store user tasks (standby + accepted)
- Store people profiles and their conversation history
- Store summaries and metadata for all past meetings
- Sync between Web App and Glasses
- Handle authentication, privacy settings, and user management