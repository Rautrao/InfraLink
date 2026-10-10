#!/usr/bin/env sh
set -eu

backup_file=${1:-"backups/infralink-$(date -u +%Y%m%dT%H%M%SZ).dump"}
mkdir -p "$(dirname "$backup_file")"
if [ -n "${DATABASE_URL:-}" ]; then
  pg_dump "$DATABASE_URL" --format=custom --file="$backup_file"
else
  docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
fi
printf 'Database backup written to %s\n' "$backup_file"
