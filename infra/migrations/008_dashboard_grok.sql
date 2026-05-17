-- Dashboard and Grok loop clip planning tables.

CREATE TABLE IF NOT EXISTS shorts_project (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'idea'
        CHECK (status IN ('idea', 'scripting', 'clips', 'assembly', 'review', 'complete', 'paused')),
    target_duration_seconds INTEGER NOT NULL DEFAULT 45 CHECK (target_duration_seconds BETWEEN 10 AND 180),
    manual_script TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shorts_project_status_created_at
    ON shorts_project(status, created_at DESC);

CREATE TABLE IF NOT EXISTS grok_clip (
    id BIGSERIAL PRIMARY KEY,
    clip_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL REFERENCES shorts_project(project_id) ON DELETE CASCADE,
    clip_index INTEGER NOT NULL CHECK (clip_index >= 1),
    title TEXT NOT NULL,
    prompt TEXT NOT NULL DEFAULT '',
    first_frame_prompt TEXT NOT NULL DEFAULT '',
    last_frame_prompt TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'prompt_ready', 'generated', 'approved', 'rejected')),
    duration_seconds INTEGER NOT NULL DEFAULT 12 CHECK (duration_seconds BETWEEN 5 AND 15),
    video_uri TEXT NOT NULL DEFAULT '',
    loop_match_notes TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, clip_index)
);

CREATE INDEX IF NOT EXISTS idx_grok_clip_project_index
    ON grok_clip(project_id, clip_index);
CREATE INDEX IF NOT EXISTS idx_grok_clip_status
    ON grok_clip(status);
