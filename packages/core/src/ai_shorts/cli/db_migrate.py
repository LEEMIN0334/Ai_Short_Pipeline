import asyncio
from pathlib import Path

from ai_shorts.storage.postgres import get_conn


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


async def apply_migrations() -> None:
    migration_dir = _repo_root() / "infra" / "migrations"
    migration_paths = sorted(migration_dir.glob("*.sql"))
    if not migration_paths:
        msg = f"No migrations found in {migration_dir}"
        raise RuntimeError(msg)

    async with get_conn() as conn:
        for migration_path in migration_paths:
            sql = migration_path.read_text(encoding="utf-8-sig")
            await conn.execute(sql)
            print(f"applied {migration_path.name}")


def main() -> None:
    asyncio.run(apply_migrations())


if __name__ == "__main__":
    main()
