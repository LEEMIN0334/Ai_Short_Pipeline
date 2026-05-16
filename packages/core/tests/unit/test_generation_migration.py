from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = ROOT_DIR / "infra" / "migrations"
GENERATION_MIGRATION = MIGRATIONS_DIR / "002_generation.sql"


def test_generation_migration_is_ordered_after_initial_migration() -> None:
    migration_names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))

    assert migration_names[:2] == ["001_initial.sql", "002_generation.sql"]


def test_generation_migration_defines_phase2_tables_and_indexes() -> None:
    sql = GENERATION_MIGRATION.read_text()

    for table_name in [
        "generation_job",
        "generated_script",
        "tts_asset",
        "script_segment",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql

    for index_name in [
        "idx_generation_job_status",
        "idx_generated_script_job_id",
        "idx_tts_asset_script_id",
        "idx_script_segment_script_scene_line",
    ]:
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql


def test_generation_migration_keeps_timeline_constraints() -> None:
    sql = GENERATION_MIGRATION.read_text()

    assert "CHECK (target_duration_ms > 0)" in sql
    assert "CHECK (scene_index >= 0)" in sql
    assert "CHECK (line_index >= 0)" in sql
    assert "CHECK (end_ms > start_ms)" in sql
