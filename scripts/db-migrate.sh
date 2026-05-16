#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$ROOT_DIR/infra/migrations}"

if [[ -z "${POSTGRES_URL:-}" ]]; then
  printf 'POSTGRES_URL is required.\n' >&2
  printf 'Example: POSTGRES_URL=postgresql://user:pass@host:5432/db %s\n' "$0" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  printf 'psql is required to run migrations.\n' >&2
  printf 'Install PostgreSQL client tools, then retry.\n' >&2
  exit 1
fi

if [[ ! -d "$MIGRATIONS_DIR" ]]; then
  printf 'Migrations directory not found: %s\n' "$MIGRATIONS_DIR" >&2
  exit 1
fi

shopt -s nullglob
migrations=("$MIGRATIONS_DIR"/*.sql)
if [[ "${#migrations[@]}" -eq 0 ]]; then
  printf 'No migration files found in %s\n' "$MIGRATIONS_DIR" >&2
  exit 1
fi

for migration in "${migrations[@]}"; do
  printf 'Applying %s\n' "${migration#$ROOT_DIR/}"
  psql "$POSTGRES_URL" -v ON_ERROR_STOP=1 -f "$migration"
done

printf 'Migrations applied successfully.\n'
