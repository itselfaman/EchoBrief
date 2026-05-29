-- ============================================================
-- EchoBrief — Complete Supabase Schema + RLS + Storage Setup
-- Run this ONCE in: Supabase Dashboard > SQL Editor
--
-- Order of operations:
--   1. Extensions
--   2. Enum types
--   3. Tables  (users → media_files → transcripts → summaries)
--   4. Triggers
--   5. RLS enable + policies
--   6. Storage policies
-- ============================================================


-- ── 1. Extensions ────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ── 2. Enum types ────────────────────────────────────────────
DO $$ BEGIN
  CREATE TYPE file_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── 3. Tables ────────────────────────────────────────────────

-- 3a. users
CREATE TABLE IF NOT EXISTS public.users (
    id          UUID        PRIMARY KEY,           -- mirrors auth.users.id
    email       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email);

-- 3b. media_files
CREATE TABLE IF NOT EXISTS public.media_files (
    id               UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID             NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    file_name        VARCHAR(500)     NOT NULL,
    storage_path     TEXT             NOT NULL,
    file_size_bytes  BIGINT           NOT NULL,
    status           file_status_enum NOT NULL DEFAULT 'pending',
    error_message    TEXT,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_media_files_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);
CREATE INDEX IF NOT EXISTS ix_media_files_user_id ON public.media_files (user_id);
CREATE INDEX IF NOT EXISTS ix_media_files_status  ON public.media_files (status);

-- 3c. transcripts
CREATE TABLE IF NOT EXISTS public.transcripts (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id    UUID        NOT NULL UNIQUE REFERENCES public.media_files (id) ON DELETE CASCADE,
    raw_text   TEXT        NOT NULL,
    segments   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_transcripts_file_id ON public.transcripts (file_id);

-- 3d. summaries
CREATE TABLE IF NOT EXISTS public.summaries (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id           UUID        NOT NULL UNIQUE REFERENCES public.media_files (id) ON DELETE CASCADE,
    executive_summary TEXT        NOT NULL,
    key_takeaways     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    action_items      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_summaries_file_id ON public.summaries (file_id);


-- ── 4. Triggers ──────────────────────────────────────────────

-- Auto-update updated_at on media_files
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_media_files_updated_at ON public.media_files;
CREATE TRIGGER trigger_media_files_updated_at
    BEFORE UPDATE ON public.media_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ── 5. RLS ───────────────────────────────────────────────────

ALTER TABLE public.users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.media_files  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.summaries    ENABLE ROW LEVEL SECURITY;

-- ── USERS policies ────────────────────────────────────────────
DROP POLICY IF EXISTS "users_select_own"        ON public.users;
DROP POLICY IF EXISTS "users_insert_own"        ON public.users;
DROP POLICY IF EXISTS "users_update_own"        ON public.users;
DROP POLICY IF EXISTS "users_service_role_all"  ON public.users;

CREATE POLICY "users_select_own"
    ON public.users FOR SELECT
    USING (id = auth.uid());

CREATE POLICY "users_insert_own"
    ON public.users FOR INSERT
    WITH CHECK (id = auth.uid());

CREATE POLICY "users_update_own"
    ON public.users FOR UPDATE
    USING (id = auth.uid());

-- Service role (backend) bypasses user-level restrictions
CREATE POLICY "users_service_role_all"
    ON public.users FOR ALL
    USING (auth.role() = 'service_role');

-- ── MEDIA_FILES policies ──────────────────────────────────────
DROP POLICY IF EXISTS "media_files_select_own"        ON public.media_files;
DROP POLICY IF EXISTS "media_files_insert_own"        ON public.media_files;
DROP POLICY IF EXISTS "media_files_delete_own"        ON public.media_files;
DROP POLICY IF EXISTS "media_files_service_role_all"  ON public.media_files;

CREATE POLICY "media_files_select_own"
    ON public.media_files FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "media_files_insert_own"
    ON public.media_files FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "media_files_delete_own"
    ON public.media_files FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "media_files_service_role_all"
    ON public.media_files FOR ALL
    USING (auth.role() = 'service_role');

-- ── TRANSCRIPTS policies ──────────────────────────────────────
DROP POLICY IF EXISTS "transcripts_select_own"        ON public.transcripts;
DROP POLICY IF EXISTS "transcripts_service_role_all"  ON public.transcripts;

CREATE POLICY "transcripts_select_own"
    ON public.transcripts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.media_files mf
            WHERE mf.id = transcripts.file_id
              AND mf.user_id = auth.uid()
        )
    );

CREATE POLICY "transcripts_service_role_all"
    ON public.transcripts FOR ALL
    USING (auth.role() = 'service_role');

-- ── SUMMARIES policies ────────────────────────────────────────
DROP POLICY IF EXISTS "summaries_select_own"        ON public.summaries;
DROP POLICY IF EXISTS "summaries_service_role_all"  ON public.summaries;

CREATE POLICY "summaries_select_own"
    ON public.summaries FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.media_files mf
            WHERE mf.id = summaries.file_id
              AND mf.user_id = auth.uid()
        )
    );

CREATE POLICY "summaries_service_role_all"
    ON public.summaries FOR ALL
    USING (auth.role() = 'service_role');


-- ── 6. Storage Policies (media-files bucket) ─────────────────
-- NOTE: Create the 'media-files' bucket manually in the Supabase
--       Dashboard → Storage → New bucket (private) if not done yet.

DROP POLICY IF EXISTS "storage_insert_own"        ON storage.objects;
DROP POLICY IF EXISTS "storage_select_own"        ON storage.objects;
DROP POLICY IF EXISTS "storage_delete_own"        ON storage.objects;
DROP POLICY IF EXISTS "storage_service_role_all"  ON storage.objects;

CREATE POLICY "storage_insert_own"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'media-files'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "storage_select_own"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'media-files'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "storage_delete_own"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'media-files'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "storage_service_role_all"
    ON storage.objects FOR ALL
    USING (
        bucket_id = 'media-files'
        AND auth.role() = 'service_role'
    );

-- ── Done ─────────────────────────────────────────────────────
-- All tables, triggers, RLS policies, and storage policies are now set up.
-- Next step: in your backend, run Alembic ONLY if you want Python to manage
-- schema changes going forward (skip `alembic upgrade head` if you ran
-- this script — the tables already exist).
