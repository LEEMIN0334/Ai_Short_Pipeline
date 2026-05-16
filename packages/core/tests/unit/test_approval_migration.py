from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = ROOT_DIR / "infra" / "migrations"
APPROVAL_MIGRATION = MIGRATIONS_DIR / "004_approval.sql"


def test_approval_migration_is_ordered_after_composition_migration() -> None:
    migration_names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))

    assert migration_names[:4] == [
        "001_initial.sql",
        "002_generation.sql",
        "003_composition.sql",
        "004_approval.sql",
    ]


def test_approval_migration_defines_phase4_tables_and_indexes() -> None:
    sql = APPROVAL_MIGRATION.read_text()

    for table_name in [
        "approval_request",
        "approval_decision",
        "approval_checklist_item",
        "final_qc_report",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql

    for index_name in [
        "idx_approval_request_status",
        "idx_approval_request_rendered_asset_id",
        "idx_approval_decision_request_created",
        "idx_approval_checklist_request_id",
        "idx_final_qc_report_target_asset_id",
    ]:
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql


def test_approval_migration_links_to_rendered_outputs() -> None:
    sql = APPROVAL_MIGRATION.read_text()

    assert "REFERENCES rendered_video(asset_id) ON DELETE CASCADE" in sql
    assert "REFERENCES composition_job(job_id) ON DELETE SET NULL" in sql
    assert "REFERENCES approval_request(request_id) ON DELETE CASCADE" in sql


def test_approval_migration_keeps_status_and_score_constraints() -> None:
    sql = APPROVAL_MIGRATION.read_text()

    expected_request_status = (
        "CHECK (status IN ('pending', 'approved', 'rejected', 'changes_requested'))"
    )
    expected_decision_status = (
        "CHECK (decision IN ('approved', 'rejected', 'changes_requested'))"
    )
    assert expected_request_status in sql
    assert expected_decision_status in sql
    assert "CHECK (overall_score >= 0 AND overall_score <= 1)" in sql
    assert "UNIQUE (request_id, item_key)" in sql
