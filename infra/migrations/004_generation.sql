-- Phase 2 generation tables.

CREATE TABLE IF NOT EXISTS generation_job (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    research_report_id TEXT NOT NULL,
    benchmark_template_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'queued', 'running', 'complete', 'failed')),
    language TEXT NOT NULL DEFAULT 'ko',
    target_duration_ms INTEGER NOT NULL CHECK (target_duration_ms > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generation_job_status
    ON generation_job(status);
CREATE INDEX IF NOT EXISTS idx_generation_job_research_report_id
    ON generation_job(research_report_id);
CREATE INDEX IF NOT EXISTS idx_generation_job_benchmark_template_id
    ON generation_job(benchmark_template_id);

CREATE TABLE IF NOT EXISTS generated_script (
    id BIGSERIAL PRIMARY KEY,
    script_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES generation_job(job_id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ko',
    target_duration_ms INTEGER NOT NULL CHECK (target_duration_ms > 0),
    scenes JSONB NOT NULL,
    prompt_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_script_job_id
    ON generated_script(job_id);
CREATE INDEX IF NOT EXISTS idx_generated_script_template_id
    ON generated_script(template_id);

CREATE TABLE IF NOT EXISTS tts_asset (
    id BIGSERIAL PRIMARY KEY,
    asset_id TEXT NOT NULL UNIQUE,
    script_id TEXT NOT NULL REFERENCES generated_script(script_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    voice_id TEXT NOT NULL,
    audio_uri TEXT NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
    transcript JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tts_asset_script_id
    ON tts_asset(script_id);
CREATE INDEX IF NOT EXISTS idx_tts_asset_provider
    ON tts_asset(provider);

CREATE TABLE IF NOT EXISTS script_segment (
    id BIGSERIAL PRIMARY KEY,
    segment_id TEXT NOT NULL UNIQUE,
    script_id TEXT NOT NULL REFERENCES generated_script(script_id) ON DELETE CASCADE,
    scene_index INTEGER NOT NULL CHECK (scene_index >= 0),
    line_index INTEGER NOT NULL CHECK (line_index >= 0),
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms > 0),
    speaker TEXT NOT NULL,
    text TEXT NOT NULL,
    emphasis_cue TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_ms > start_ms)
);

CREATE INDEX IF NOT EXISTS idx_script_segment_script_scene_line
    ON script_segment(script_id, scene_index, line_index);
