-- Phase 3 composition tables.

CREATE TABLE IF NOT EXISTS composition_job (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    script_id TEXT NOT NULL REFERENCES generated_script(script_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'queued', 'running', 'rendering', 'complete', 'failed')),
    output_ratio TEXT NOT NULL DEFAULT '9:16',
    fps INTEGER NOT NULL DEFAULT 30 CHECK (fps > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_composition_job_status
    ON composition_job(status);
CREATE INDEX IF NOT EXISTS idx_composition_job_script_id
    ON composition_job(script_id);

CREATE TABLE IF NOT EXISTS composition_manifest (
    id BIGSERIAL PRIMARY KEY,
    manifest_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES composition_job(job_id) ON DELETE CASCADE,
    script_id TEXT NOT NULL REFERENCES generated_script(script_id) ON DELETE CASCADE,
    output_ratio TEXT NOT NULL DEFAULT '9:16',
    fps INTEGER NOT NULL DEFAULT 30 CHECK (fps > 0),
    manifest JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_composition_manifest_job_id
    ON composition_manifest(job_id);
CREATE INDEX IF NOT EXISTS idx_composition_manifest_script_id
    ON composition_manifest(script_id);

CREATE TABLE IF NOT EXISTS composition_segment (
    id BIGSERIAL PRIMARY KEY,
    segment_id TEXT NOT NULL UNIQUE,
    manifest_id TEXT NOT NULL REFERENCES composition_manifest(manifest_id) ON DELETE CASCADE,
    script_segment_id TEXT REFERENCES script_segment(segment_id) ON DELETE SET NULL,
    segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
    video_uri TEXT NOT NULL,
    video_mime_type TEXT NOT NULL,
    voiceover_uri TEXT,
    voiceover_mime_type TEXT,
    subtitle_ass TEXT,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_ms > start_ms)
);

CREATE INDEX IF NOT EXISTS idx_composition_segment_manifest_index
    ON composition_segment(manifest_id, segment_index);
CREATE INDEX IF NOT EXISTS idx_composition_segment_script_segment_id
    ON composition_segment(script_segment_id);

CREATE TABLE IF NOT EXISTS rendered_video (
    id BIGSERIAL PRIMARY KEY,
    asset_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES composition_job(job_id) ON DELETE CASCADE,
    manifest_id TEXT NOT NULL REFERENCES composition_manifest(manifest_id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'ffmpeg',
    output_uri TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'video/mp4',
    duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rendered_video_job_id
    ON rendered_video(job_id);
CREATE INDEX IF NOT EXISTS idx_rendered_video_manifest_id
    ON rendered_video(manifest_id);
