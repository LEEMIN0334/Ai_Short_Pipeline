-- Phase 1 collection and research tables.

CREATE TABLE IF NOT EXISTS account_pool (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'cooldown', 'blocked', 'disabled')),
    session_ref TEXT,
    rate_limit_reset_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, handle)
);

CREATE INDEX IF NOT EXISTS idx_account_pool_platform_status
    ON account_pool(platform, status);

CREATE TABLE IF NOT EXISTS channel (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_platform_handle
    ON channel(platform, handle);

CREATE TABLE IF NOT EXISTS persona_doc (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trend_item (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    channel_id BIGINT REFERENCES channel(id) ON DELETE SET NULL,
    view_count BIGINT CHECK (view_count IS NULL OR view_count >= 0),
    like_count BIGINT CHECK (like_count IS NULL OR like_count >= 0),
    comment_count BIGINT CHECK (comment_count IS NULL OR comment_count >= 0),
    share_count BIGINT CHECK (share_count IS NULL OR share_count >= 0),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms > 0),
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, source_id)
);

CREATE INDEX IF NOT EXISTS idx_trend_item_platform_collected_at
    ON trend_item(platform, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_trend_item_published_at
    ON trend_item(published_at DESC);

CREATE TABLE IF NOT EXISTS scored_trend_item (
    id BIGSERIAL PRIMARY KEY,
    trend_item_id BIGINT NOT NULL REFERENCES trend_item(id) ON DELETE CASCADE,
    viral_score NUMERIC(12, 6) NOT NULL CHECK (viral_score >= 0),
    category TEXT NOT NULL,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trend_item_id)
);

CREATE INDEX IF NOT EXISTS idx_scored_trend_item_score
    ON scored_trend_item(viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_scored_trend_item_category
    ON scored_trend_item(category);

CREATE TABLE IF NOT EXISTS benchmark_template (
    id BIGSERIAL PRIMARY KEY,
    trend_item_id BIGINT REFERENCES trend_item(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
    scenes JSONB NOT NULL DEFAULT '[]'::jsonb,
    copy_button_text TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_benchmark_template_category
    ON benchmark_template(category);

CREATE TABLE IF NOT EXISTS research_report (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    report_ref TEXT,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(summary, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(body_markdown, '')), 'C')
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_report_search_vector
    ON research_report USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_research_report_created_at
    ON research_report(created_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'public'
              AND tablename = 'cost_log'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE cost_log;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'public'
              AND tablename = 'trend_item'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE trend_item;
        END IF;
    END IF;
END $$;
