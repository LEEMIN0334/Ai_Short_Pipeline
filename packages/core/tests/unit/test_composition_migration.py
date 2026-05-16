from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = ROOT_DIR / "infra" / "migrations"
COMPOSITION_MIGRATION = MIGRATIONS_DIR / "005_composition.sql"


def test_composition_migration_is_ordered_after_generation_migration() -> None:
    migration_names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))

    assert migration_names[:5] == [
        "001_initial.sql",
        "002_phase1_collection.sql",
        "003_phase1_orchestration.sql",
        "004_generation.sql",
        "005_composition.sql",
    ]


def test_composition_migration_defines_phase3_tables_and_indexes() -> None:
    sql = COMPOSITION_MIGRATION.read_text()

    for table_name in [
        "composition_job",
        "composition_manifest",
        "composition_segment",
        "rendered_video",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql

    for index_name in [
        "idx_composition_job_status",
        "idx_composition_job_script_id",
        "idx_composition_manifest_job_id",
        "idx_composition_segment_manifest_index",
        "idx_rendered_video_job_id",
    ]:
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql


def test_composition_migration_links_to_generation_outputs() -> None:
    sql = COMPOSITION_MIGRATION.read_text()

    assert "REFERENCES generated_script(script_id) ON DELETE CASCADE" in sql
    assert "REFERENCES script_segment(segment_id) ON DELETE SET NULL" in sql
    assert "REFERENCES composition_manifest(manifest_id) ON DELETE CASCADE" in sql


def test_composition_migration_keeps_rendering_constraints() -> None:
    sql = COMPOSITION_MIGRATION.read_text()

    expected_status_check = (
        "CHECK (status IN ('draft', 'queued', 'running', 'rendering', 'complete', 'failed'))"
    )
    assert expected_status_check in sql
    assert "CHECK (fps > 0)" in sql
    assert "CHECK (segment_index >= 0)" in sql
    assert "CHECK (end_ms > start_ms)" in sql
    assert "CHECK (width > 0)" in sql
    assert "CHECK (height > 0)" in sql
