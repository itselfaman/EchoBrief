# EchoBrief — Complete Stack Setup Guide

> Production-grade AI media transcription & summarization platform.
> **Stack:** React.js · FastAPI · PostgreSQL · Supabase Auth · Redis · Dramatiq · OpenAI Whisper · Gemini Flash

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [External Services Setup](#2-external-services-setup)
3. [Backend Setup (FastAPI + uv)](#3-backend-setup-fastapi--uv)
4. [Database Migration](#4-database-migration)
5. [Start the Worker (Dramatiq)](#5-start-the-worker-dramatiq)
6. [Frontend Setup (React + Vite)](#6-frontend-setup-react--vite)
7. [Running Everything Together](#7-running-everything-together)
8. [Testing the Full Flow](#8-testing-the-full-flow)
9. [Architecture Reference](#9-architecture-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

Install these tools before starting:

| Tool | Min Version | Install |
|------|-------------|---------|
| Python | 3.11+ | https://python.org |
| uv | latest | `pip install uv` or https://docs.astral.sh/uv |
| Node.js | 20+ | https://nodejs.org |
| Redis | 7+ | https://redis.io/download (Windows: use WSL or Docker) |
| ffmpeg | latest | https://ffmpeg.org/download.html — **required for large file chunking** |
| Git | any | https://git-scm.com |

### Redis on Windows (easiest)
```powershell
# Option A: Docker Desktop (recommended)
docker compose up redis -d

# Option B: WSL2
wsl --install
# inside WSL: sudo apt install redis-server && redis-server
```

### Verify prerequisites
```powershell
python --version    # Python 3.11+
uv --version
node --version      # v20+
redis-cli ping      # PONG
ffmpeg -version
```

---

## 2. External Services Setup

### 2.1 Supabase Project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Choose a region close to you, set a strong DB password
3. Wait ~2 minutes for provisioning

**Collect these values** (from Dashboard → Settings → API):
- **Project URL**: `https://xxxxxxxxxxxx.supabase.co`
- **Anon/Public Key**: starts with `eyJhbGci...`
- **Service Role Key**: starts with `eyJhbGci...` (keep secret!)
- **JWT Secret**: Dashboard → Settings → API → JWT Secret

**Create Storage Bucket:**
1. Supabase Dashboard → Storage → New Bucket
2. Name: `media-files`
3. Check **"Allow authenticated uploads"**
4. Set max file size: `10737418240` (10 GB)

**Set Storage Policy** (Supabase Dashboard → Storage → media-files → Policies):
```sql
-- Allow authenticated users to upload to their own folder
CREATE POLICY "Users can upload own media" ON storage.objects
  FOR INSERT WITH CHECK (
    bucket_id = 'media-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );

-- Allow users to read their own files
CREATE POLICY "Users can read own media" ON storage.objects
  FOR SELECT USING (
    bucket_id = 'media-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );

-- Allow service role full access (for workers)
CREATE POLICY "Service role full access" ON storage.objects
  USING (auth.role() = 'service_role');
```

**Get your Database Connection String** (Dashboard → Settings → Database → Connection string → URI):
- Select **Transaction mode** for the pooler connection
- Replace `[YOUR-PASSWORD]` with your DB password
- Change scheme from `postgresql://` to `postgresql+asyncpg://`

Example:
```
postgresql+asyncpg://postgres.xxxxxxxxxxxx:YOUR_PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

### 2.2 OpenAI API Key
1. Go to [platform.openai.com](https://platform.openai.com)
2. API Keys → Create new key
3. Add at least $5 credit (Whisper transcription costs ~$0.006/minute)

### 2.3 Google Gemini API Key (FREE)
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Create API Key → select your Google Cloud project
3. **Gemini 1.5 Flash free tier:** 15 RPM · 1M TPM · 1,500 req/day — no credit card needed!

---

## 3. Backend Setup (FastAPI + uv)

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment and install dependencies
uv sync

# Copy environment template
copy .env.example .env
```

**Edit `backend/.env`** with your real values:
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxx:password@host:6543/postgres
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
SUPABASE_STORAGE_BUCKET=media-files

REDIS_HOST=localhost
REDIS_PORT=6379

OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIza...

MAX_FILE_SIZE_BYTES=10737418240
TEMP_MEDIA_DIR=C:/temp/echobrief
ALLOWED_ORIGINS=http://localhost:5173
```

**Start the FastAPI development server:**
```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ API is running at: http://localhost:8000  
✅ Interactive docs: http://localhost:8000/docs

---

## 4. Database Migration

Run this **once** to create all tables:

```powershell
cd backend
uv run alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema — users, media_files, transcripts, summaries
```

**Verify tables exist** (in Supabase Dashboard → Table Editor):
- `users`
- `media_files`
- `transcripts`
- `summaries`

To create a new migration after model changes:
```powershell
uv run alembic revision --autogenerate -m "describe your change"
uv run alembic upgrade head
```

---

## 5. Start the Worker (Dramatiq)

The Dramatiq worker is a **separate process** that picks up jobs from Redis.

```powershell
# In a new terminal (while FastAPI is running in another)
cd backend
uv run dramatiq app.workers.tasks --processes 2 --threads 4 --queues echobrief_processing
```

Parameters:
- `--processes 2`: 2 worker processes
- `--threads 4`: 4 threads per process (8 concurrent jobs max)
- `--queues echobrief_processing`: only process our queue

For development (auto-reload on code changes):
```powershell
uv run dramatiq app.workers.tasks --watch app --queues echobrief_processing
```

Worker logs will show:
```
[2024-01-15 10:30:00,123] [MainThread] INFO: Starting media processing file_id=xxx
[2024-01-15 10:30:01,456] [MainThread] INFO: Transcription complete char_count=15234
[2024-01-15 10:30:03,789] [MainThread] INFO: Summarization complete file_id=xxx
[2024-01-15 10:30:03,890] [MainThread] INFO: Media processing completed successfully
```

---

## 6. Frontend Setup (React + Vite)

```powershell
cd frontend

# Install dependencies
npm install

# Copy environment template
copy .env.example .env
```

**Edit `frontend/.env`**:
```env
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGci...
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_STORAGE_BUCKET=media-files
```

**Start the dev server:**
```powershell
npm run dev
```

✅ Frontend running at: http://localhost:5173

---

## 7. Running Everything Together

Open **4 terminal windows**:

| Terminal | Command | Purpose |
|----------|---------|---------|
| 1 | `cd backend && uv run uvicorn app.main:app --reload` | FastAPI API server |
| 2 | `cd backend && uv run dramatiq app.workers.tasks --watch app --queues echobrief_processing` | Worker process |
| 3 | `cd frontend && npm run dev` | React dev server |
| 4 | `redis-cli ping` then keep open for monitoring | Redis check |

Or start Redis via Docker (if not running locally):
```powershell
docker compose up redis -d
```

---

## 8. Testing the Full Flow

### Step 1: Register / Sign In
1. Open http://localhost:5173
2. Sign up with your email
3. Check your email for confirmation (Supabase sends one)

### Step 2: Upload a File
1. Drag an `.mp3` or `.mp4` file onto the upload zone
2. Watch the progress bar fill as it uploads to Supabase Storage
3. After upload, the file appears in your dashboard with status **Pending**

### Step 3: Watch Processing
1. Status transitions: `Pending → Processing → Completed`
2. The dashboard auto-polls every 5 seconds
3. Worker terminal shows transcription/summarization logs

### Step 4: View Results
1. Click **"View Results →"** on a completed file
2. See the **Executive Summary** tab with:
   - Narrative summary paragraph
   - Key takeaways with categories (insight/decision/risk/opportunity)
   - Action items with owner and priority
3. Click **Transcript** tab to see the full text

### Test the API directly:
```powershell
# Health check
curl http://localhost:8000/health

# API docs
start http://localhost:8000/docs
```

---

## 9. Architecture Reference

```
                    ┌─────────────────────────────────────────┐
                    │           React.js Frontend              │
                    │  (Vite · Supabase JS SDK · TanStack Q)  │
                    └────────────┬───────────┬─────────────────┘
                                 │ API calls │ Direct upload
                                 │ (Axios)   │ to Supabase Storage
                    ┌────────────▼───────────▼─────────────────┐
                    │         Supabase Storage                  │
                    │    (S3-compatible, up to 10 GB)           │
                    └───────────────────────────────────────────┘
                                 │ JWT Auth
                    ┌────────────▼─────────────────────────────┐
                    │           FastAPI Backend                 │
                    │  ┌─────────┐  ┌──────────┐  ┌────────┐  │
                    │  │MediaSvc │  │TranscrSvc│  │SumSvc  │  │
                    │  └────┬────┘  └────┬─────┘  └───┬────┘  │
                    │       │            │              │       │
                    │  ┌────▼────────────▼──────────────▼───┐  │
                    │  │       PostgreSQL (Supabase DB)       │  │
                    │  └──────────────────────────────────────┘  │
                    │       │ Enqueue job                    │
                    │  ┌────▼──────┐                        │
                    │  │  Redis    │ ← Message Broker        │
                    │  └────┬──────┘                        │
                    └───────┼───────────────────────────────┘
                            │ Task pulled by worker
                    ┌───────▼───────────────────────────────────┐
                    │         Dramatiq Worker Process            │
                    │  1. Download from Supabase Storage         │
                    │  2. Transcribe → OpenAI Whisper API        │
                    │  3. Summarize  → Gemini 1.5 Flash (free)  │
                    │  4. Save Transcript + Summary to DB        │
                    │  5. Update status → 'completed'            │
                    └───────────────────────────────────────────┘
```

### DB Schema

```sql
users          (id UUID PK, email, created_at)
  ↓ 1:N
media_files    (id, user_id FK, file_name, storage_path, file_size_bytes,
                status ENUM, error_message, created_at, updated_at)
  ↓ 1:1                ↓ 1:1
transcripts    summaries
(file_id UNIQUE,      (file_id UNIQUE,
 raw_text,             executive_summary,
 segments JSONB,       key_takeaways JSONB,
 created_at)           action_items JSONB,
                       created_at)
```

---

## 10. Troubleshooting

### ❌ "DATABASE_URL must use the asyncpg driver"
Make sure your DATABASE_URL starts with `postgresql+asyncpg://` (not `postgresql://`)

### ❌ "SUPABASE_URL must be an HTTPS URL"
Check that your SUPABASE_URL starts with `https://` and ends without a trailing slash

### ❌ Redis connection refused
```powershell
# Start Redis via Docker
docker compose up redis -d
# or start local Redis service
redis-server
```

### ❌ Whisper transcription fails for large files
Install ffmpeg and ensure it's in your PATH:
```powershell
winget install FFmpeg
# Restart your terminal
ffmpeg -version
```

### ❌ Gemini returns invalid JSON
The worker strips markdown fences from Gemini's response. If it still fails, reduce `max_output_tokens` in `tasks.py` or check your `GEMINI_API_KEY`.

### ❌ CORS errors in browser
Add your frontend URL to `ALLOWED_ORIGINS` in `backend/.env`:
```
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### ❌ Worker not picking up tasks
Verify the queue name matches:
```powershell
# Worker should listen to echobrief_processing queue
uv run dramatiq app.workers.tasks --queues echobrief_processing
```

### ❌ Supabase JWT verification fails
Go to Supabase Dashboard → Settings → API → JWT Settings  
Copy the **JWT Secret** (not the anon key) into `SUPABASE_JWT_SECRET`

---

## Environment Variables Quick Reference

### Backend (`backend/.env`)
| Variable | Required | Example |
|----------|----------|---------|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://...` |
| `SUPABASE_URL` | ✅ | `https://xxx.supabase.co` |
| `SUPABASE_ANON_KEY` | ✅ | `eyJhbGci...` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | `eyJhbGci...` |
| `SUPABASE_JWT_SECRET` | ✅ | `your-jwt-secret` |
| `REDIS_HOST` | ✅ | `localhost` |
| `OPENAI_API_KEY` | ✅ | `sk-proj-...` |
| `GEMINI_API_KEY` | ✅ | `AIza...` |

### Frontend (`frontend/.env`)
| Variable | Required | Example |
|----------|----------|---------|
| `VITE_SUPABASE_URL` | ✅ | `https://xxx.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | ✅ | `eyJhbGci...` |
| `VITE_API_BASE_URL` | ✅ | `http://localhost:8000` |
| `VITE_SUPABASE_STORAGE_BUCKET` | ✅ | `media-files` |

---

*Built with ❤️ on the `feature/basic_structure` branch*
