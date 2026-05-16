-- Phase 4 approval flow tables.

CREATE TABLE IF NOT EXISTS approval_request (
    id BIGSERIAL PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    composition_job_id TEXT REFERENCES composition_job(job_id) ON DELETE SET NULL,
    rendered_asset_id TEXT NOT NULL REFERENCES rendered_video(asset_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'changes_requested')),
    requested_by TEXT NOT NULL,
    reviewer_id TEXT,
    review_url TEXT,
    due_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_request_status
    ON approval_request(status);
CREATE INDEX IF NOT EXISTS idx_approval_request_rendered_asset_id
    ON approval_request(rendered_asset_id);
CREATE INDEX IF NOT EXISTS idx_approval_request_reviewer_id
    ON approval_request(reviewer_id);

CREATE TABLE IF NOT EXISTS approval_decision (
    id BIGSERIAL PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL REFERENCES approval_request(request_id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
    comment TEXT NOT NULL DEFAULT '',
    required_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_decision_request_created
    ON approval_decision(request_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_decision_actor_id
    ON approval_decision(actor_id);

CREATE TABLE IF NOT EXISTS approval_checklist_item (
    id BIGSERIAL PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES approval_request(request_id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    label TEXT NOT NULL,
    passed BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (request_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_approval_checklist_request_id
    ON approval_checklist_item(request_id);

CREATE TABLE IF NOT EXISTS final_qc_report (
    id BIGSERIAL PRIMARY KEY,
    report_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL REFERENCES approval_request(request_id) ON DELETE CASCADE,
    target_asset_id TEXT NOT NULL REFERENCES rendered_video(asset_id) ON DELETE CASCADE,
    overall_score NUMERIC(4, 3) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 1),
    passed BOOLEAN NOT NULL,
    scores JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_fixes JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_final_qc_report_request_id
    ON final_qc_report(request_id);
CREATE INDEX IF NOT EXISTS idx_final_qc_report_target_asset_id
    ON final_qc_report(target_asset_id);
