# Database Schema

This document describes the database schema used in the Junction2025 backend.

## Overview

The schema consists of **4 main tables**:
1. `meetings` - Stores meeting sessions and their data
2. `tasks` - Stores extracted tasks from meetings
3. `speakers` - Stores known speakers for speaker diarization
4. `user_settings` - Stores user preferences and settings

---

## Table: `meetings`

Stores meeting session information, transcripts, summaries, and associated tasks.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PRIMARY KEY | Unique meeting identifier (UUID) |
| `start_time` | DateTime | NOT NULL, DEFAULT now() | When the meeting started |
| `end_time` | DateTime | NULLABLE | When the meeting ended |
| `status` | String | NOT NULL, DEFAULT 'active' | Meeting status: `active`, `completed`, `cancelled` |
| `summary` | Text | NULLABLE | LLM-generated meeting summary |
| `transcript` | JSON | NOT NULL, DEFAULT [] | Array of transcript segments |
| `tasks` | JSON | NOT NULL, DEFAULT [] | Array of associated tasks |
| `created_at` | DateTime | NOT NULL, DEFAULT now() | Record creation timestamp |
| `updated_at` | DateTime | NOT NULL, DEFAULT now() | Last update timestamp (auto-updated) |

### Transcript JSON Structure

Each transcript segment in the `transcript` JSON array has this structure:

```json
{
  "text": "Hello, how are you?",
  "speaker": "John Doe",
  "start": 0.5,
  "end": 2.3,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Tasks JSON Structure

Each task in the `tasks` JSON array has this structure:

```json
{
  "task_id": "uuid-here",
  "description": "Follow up with client",
  "assignee": "John Doe",
  "due_date": "2025-01-20",
  "status": "pending",
  "priority": "high",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

## Table: `tasks`

Stores individual tasks extracted from meetings (normalized from JSON in meetings table).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PRIMARY KEY | Unique task identifier (UUID) |
| `meeting_id` | String | NOT NULL, INDEXED | Foreign key to `meetings.id` |
| `description` | Text | NOT NULL | Task description |
| `assignee` | String | NULLABLE | Person assigned to the task |
| `due_date` | DateTime | NULLABLE | Task due date |
| `status` | String | NOT NULL, DEFAULT 'pending' | Task status: `pending`, `in_progress`, `completed` |
| `priority` | String | NOT NULL, DEFAULT 'medium' | Task priority: `high`, `medium`, `low` |
| `created_at` | DateTime | NOT NULL, DEFAULT now() | Record creation timestamp |
| `updated_at` | DateTime | NOT NULL, DEFAULT now() | Last update timestamp (auto-updated) |

**Note:** Tasks are stored both in the `meetings.tasks` JSON array (for quick access) and in this normalized table (for better querying and relationships).

---

## Table: `speakers`

Stores known speakers for improved speaker diarization accuracy.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PRIMARY KEY | Unique speaker identifier (UUID) |
| `name` | String | NOT NULL, UNIQUE | Speaker's name |
| `audio_reference` | Text | NULLABLE | Path or data URL to voice sample |
| `created_at` | DateTime | NOT NULL, DEFAULT now() | Record creation timestamp |

**Usage:** When a speaker is registered, their voice sample is used by the STT service to improve speaker identification accuracy.

---

## Table: `user_settings`

Stores user preferences and settings, including language preferences.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PRIMARY KEY | Unique settings identifier (UUID) |
| `user_id` | String | NOT NULL, UNIQUE, INDEXED | User identifier (unique per user) |
| `spoken_languages` | JSON | NOT NULL, DEFAULT [] | Array of language codes the user speaks (e.g., `["en", "pt", "es"]`) |
| `preferred_language` | String | NULLABLE | Preferred language code for UI/translation (e.g., `"en"`) |
| `created_at` | DateTime | NOT NULL, DEFAULT now() | Record creation timestamp |
| `updated_at` | DateTime | NOT NULL, DEFAULT now() | Last update timestamp (auto-updated) |

### Spoken Languages JSON Structure

The `spoken_languages` field is a JSON array of ISO 639-1 language codes:

```json
["en", "pt", "es", "fr"]
```

Common language codes:
- `en` - English
- `pt` - Portuguese
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `ja` - Japanese
- `zh` - Chinese
- `ko` - Korean

**Usage:** These settings are used to:
- Configure speech-to-text language detection
- Set preferred language for transcriptions and summaries
- Personalize the user experience

---

## Relationships

```
meetings (1) ──< (many) tasks
```

- One meeting can have many tasks
- Tasks reference meetings via `meeting_id`

---

## Indexes

- `tasks.meeting_id` - Indexed for fast lookups of tasks by meeting
- `speakers.name` - Unique index for speaker name lookups
- `user_settings.user_id` - Unique index for user settings lookups

---

## Example Queries

### Get all meetings
```sql
SELECT * FROM meetings ORDER BY created_at DESC;
```

### Get meeting with tasks
```sql
SELECT m.*, t.* 
FROM meetings m
LEFT JOIN tasks t ON t.meeting_id = m.id
WHERE m.id = 'meeting-uuid';
```

### Get active meetings
```sql
SELECT * FROM meetings WHERE status = 'active';
```

### Get tasks for a meeting
```sql
SELECT * FROM tasks WHERE meeting_id = 'meeting-uuid' ORDER BY created_at;
```

### Get all known speakers
```sql
SELECT * FROM speakers ORDER BY name;
```

### Get user settings
```sql
SELECT * FROM user_settings WHERE user_id = 'user-id';
```

### Update user settings
```sql
UPDATE user_settings 
SET spoken_languages = '["en", "pt"]', 
    preferred_language = 'en',
    updated_at = now()
WHERE user_id = 'user-id';
```

---

## Data Flow

1. **Meeting Start:**
   - New record created in `meetings` table
   - `status` = `'active'`
   - `transcript` = `[]`
   - `tasks` = `[]`

2. **During Meeting:**
   - Audio chunks processed → transcript segments added to `meetings.transcript` JSON array
   - Background tasks periodically:
     - Generate summaries → update `meetings.summary`
     - Extract tasks → add to `meetings.tasks` JSON array AND create records in `tasks` table

3. **Meeting End:**
   - `status` = `'completed'`
   - `end_time` = current timestamp
   - Final summary generated if not already done

---

## Migration Notes

When you first run the application with a database configured, the tables are automatically created via:

```python
Base.metadata.create_all(bind=engine)
```

This happens in the `init_db()` function, which is called on application startup.

---

## Future Enhancements

Potential additions to the schema:

- `users` table - For user authentication and multi-user support (user_settings.user_id would reference this)
- `meeting_participants` table - Track who attended meetings
- `meeting_tags` table - Categorize meetings
- `task_comments` table - Add comments to tasks
- `speaker_voice_embeddings` table - Store voice embeddings for better matching

