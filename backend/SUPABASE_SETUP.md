# Supabase Setup Guide

## Why Supabase?

Supabase is the recommended database for this project because:
- ✅ Used by Snapchat Spectacles
- ✅ Built on PostgreSQL (fully compatible)
- ✅ Free tier available
- ✅ Built-in connection pooling
- ✅ Real-time subscriptions (can be used for WebSocket alternative)
- ✅ Easy to set up and manage

## Quick Setup

### 1. Create Supabase Project

1. Go to https://supabase.com
2. Sign up or log in
3. Click **New Project**
4. Fill in:
   - **Name**: `junction2025` (or your preferred name)
   - **Database Password**: Choose a strong password (save it!)
   - **Region**: Choose closest to your users
5. Click **Create new project**
6. Wait 2-3 minutes for project to initialize

### 2. Get Connection String

1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll to **Connection string** section
3. Select **Connection pooling** tab (recommended for production)
4. Copy the connection string
5. Replace `[YOUR-PASSWORD]` with your database password

**Example connection string:**
```
postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### 3. Configure Backend

Add to your `.env` file:

```env
DATABASE_URL=postgresql://postgres.abcdefghijklmnop:your_password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### 4. Initialize Database Tables

When you start the backend server, it will automatically create the required tables:
- `meetings` - Meeting records
- `tasks` - Extracted tasks
- `speakers` - Known speakers

You can verify tables were created in Supabase Dashboard → **Table Editor**.

## Connection Modes

### Connection Pooling (Recommended)
- **Port**: 6543
- **Use case**: Production, serverless, high concurrency
- **Format**: `postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`

### Direct Connection
- **Port**: 5432
- **Use case**: Development, migrations, admin tasks
- **Format**: `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

## Database Schema

The following tables are automatically created:

### `meetings`
- `id` (String, Primary Key)
- `start_time` (DateTime)
- `end_time` (DateTime, nullable)
- `status` (String: active, completed, cancelled)
- `summary` (Text, nullable)
- `transcript` (JSON array)
- `tasks` (JSON array)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### `tasks`
- `id` (String, Primary Key)
- `meeting_id` (String, indexed)
- `description` (Text)
- `assignee` (String, nullable)
- `due_date` (DateTime, nullable)
- `status` (String: pending, in_progress, completed)
- `priority` (String: high, medium, low)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### `speakers`
- `id` (String, Primary Key)
- `name` (String, unique)
- `audio_reference` (Text, nullable)
- `created_at` (DateTime)

## Verifying Connection

1. Start your backend server:
   ```bash
   python main.py
   ```

2. Check the startup logs - you should see:
   ```
   Database initialized successfully
   ```

3. Visit Supabase Dashboard → **Table Editor** to see the created tables

## Troubleshooting

### "Database not available" error
- Check your `.env` file has `DATABASE_URL` set correctly
- Verify the password in the connection string matches your Supabase database password
- Make sure your IP is allowed (Supabase allows all by default, but check if you have restrictions)

### SSL connection error
- Supabase requires SSL connections
- The code automatically sets `sslmode=require`
- If you still get errors, check your network/firewall settings

### Connection timeout
- Use the **Connection pooling** mode (port 6543) instead of direct connection
- Check your network connection
- Verify the region matches your location

## Supabase Features You Can Use

### Real-time Subscriptions
Supabase has built-in real-time subscriptions that can complement or replace WebSocket:

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase.table('meetings').on('UPDATE', handle_update).subscribe()
```

### Row Level Security (RLS)
You can add RLS policies to secure your data:
- Only allow users to see their own meetings
- Restrict task access by team
- Control speaker data access

### Storage
Use Supabase Storage for audio files:
- Store speaker voice samples
- Archive meeting recordings
- Store meeting transcripts

## Next Steps

1. ✅ Database is set up and connected
2. ✅ Tables are created automatically
3. 🔄 Consider adding Row Level Security policies
4. 🔄 Set up Supabase Storage for audio files
5. 🔄 Configure backups (Supabase handles this automatically)

## Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Python Client](https://github.com/supabase/supabase-py)
- [PostgreSQL Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)

