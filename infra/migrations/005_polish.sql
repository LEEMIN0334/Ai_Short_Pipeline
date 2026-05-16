-- Phase 5 polish and self-analytics tables.

CREATE TABLE IF NOT EXISTS polish_job (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    approval_request_id TEXT REFERENCES approval_request(request_id) ON DELETE SET NULL,
    source_asset_id TEXT NOT NULL REFERENCES rendered_video(asset_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'queued', 'running', 'complete', 'failed')),
    goal TEXT NOT NULL DEFAULT 'polish',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polish_job_status
    ON polish_job(status);
CREATE INDEX IF NOT EXISTS idx_polish_job_source_asset_id
    ON polish_job(source_asset_id);
CREATE INDEX IF NOT EXISTS idx_polish_job_approval_request_id
    ON polish_job(approval_request_id);

CREATE TABLE IF NOT EXISTS polish_variant (
    id BIGSERIAL PRIMARY KEY,
    variant_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES polish_job(job_id) ON DELETE CASCADE,
    output_uri TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'video/mp4',
    duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
    variant_rank INTEGER NOT NULL DEFAULT 0 CHECK (variant_rank >= 0),
    changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    qc_report JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polish_variant_job_rank
    ON polish_variant(job_id, variant_rank);

CREATE TABLE IF NOT EXISTS analytics_event (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    asset_id TEXT NOT NULL REFERENCES rendered_video(asset_id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_value NUMERIC(18, 6) NOT NULL DEFAULT 1 CHECK (event_value >= 0),
    occurred_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_event_asset_platform
    ON analytics_event(asset_id, platform);
CREATE INDEX IF NOT EXISTS idx_analytics_event_type_time
    ON analytics_event(event_type, occurred_at DESC);

CREATE TABLE IF NOT EXISTS performance_snapshot (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL UNIQUE,
    asset_id TEXT NOT NULL REFERENCES rendered_video(asset_id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    view_count BIGINT NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    like_count BIGINT NOT NULL DEFAULT 0 CHECK (like_count >= 0),
    comment_count BIGINT NOT NULL DEFAULT 0 CHECK (comment_count >= 0),
    share_count BIGINT NOT NULL DEFAULT 0 CHECK (share_count >= 0),
    watch_time_seconds NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (watch_time_seconds >= 0),
    captured_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_performance_snapshot_asset_platform
    ON performance_snapshot(asset_id, platform, captured_at DESC);
