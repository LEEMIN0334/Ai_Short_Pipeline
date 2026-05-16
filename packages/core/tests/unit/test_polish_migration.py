from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = ROOT_DIR / "infra" / "migrations"
POLISH_MIGRATION = MIGRATIONS_DIR / "007_polish.sql"


def test_polish_migration_is_ordered_after_approval_migration() -> None:
    migration_names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))

    assert migration_names[:7] == [
        "001_initial.sql",
        "002_phase1_collection.sql",
        "003_phase1_orchestration.sql",
        "004_generation.sql",
        "005_composition.sql",
        "006_approval.sql",
        "007_polish.sql",
    ]


def test_polish_migration_defines_phase5_tables_and_indexes() -> None:
    sql = POLISH_MIGRATION.read_text()

    for table_name in [
        "polish_job",
        "polish_variant",
        "analytics_event",
        "performance_snapshot",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql

    for index_name in [
        "idx_polish_job_status",
        "idx_polish_variant_job_rank",
        "idx_analytics_event_asset_platform",
        "idx_performance_snapshot_asset_platform",
    ]:
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql


def test_polish_migration_links_to_approval_and_rendered_assets() -> None:
    sql = POLISH_MIGRATION.read_text()

    assert "REFERENCES approval_request(request_id) ON DELETE SET NULL" in sql
    assert "REFERENCES rendered_video(asset_id) ON DELETE CASCADE" in sql
    assert "REFERENCES polish_job(job_id) ON DELETE CASCADE" in sql


def test_polish_migration_keeps_status_and_metric_constraints() -> None:
    sql = POLISH_MIGRATION.read_text()

    assert "CHECK (status IN ('draft', 'queued', 'running', 'complete', 'failed'))" in sql
    assert "CHECK (variant_rank >= 0)" in sql
    assert "CHECK (event_value >= 0)" in sql
    assert "CHECK (view_count >= 0)" in sql
    assert "CHECK (watch_time_seconds >= 0)" in sql
