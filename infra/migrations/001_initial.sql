-- Phase 0 foundation tables.

CREATE TABLE IF NOT EXISTS cost_log (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    service TEXT NOT NULL,
    operation TEXT NOT NULL,
    usd NUMERIC(12, 6) NOT NULL CHECK (usd >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_log_job_id ON cost_log(job_id);
CREATE INDEX IF NOT EXISTS idx_cost_log_created_at ON cost_log(created_at DESC);

CREATE TABLE IF NOT EXISTS cost_estimate (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    estimate JSONB NOT NULL,
    estimated_usd NUMERIC(12, 6) NOT NULL CHECK (estimated_usd >= 0),
    user_confirmed_at TIMESTAMPTZ,
    actual_usd NUMERIC(12, 6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_estimate_job_id ON cost_estimate(job_id);

CREATE TABLE IF NOT EXISTS conversation (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    body TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_thread_created_at
    ON conversation(thread_id, created_at);
