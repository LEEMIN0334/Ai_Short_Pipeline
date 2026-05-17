-- Always-on agent runtime tables.

CREATE TABLE IF NOT EXISTS agent_registry (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'worker',
    status TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'paused', 'offline', 'error')),
    capabilities TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    heartbeat_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_status
    ON agent_registry(status, heartbeat_at DESC);

CREATE TABLE IF NOT EXISTS agent_task (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    requested_by TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    command TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 0,
    result TEXT NOT NULL DEFAULT '',
    error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_task_status_created_at
    ON agent_task(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_task_agent_status
    ON agent_task(agent_id, status, priority DESC, created_at);
