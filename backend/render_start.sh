#!/bin/sh
set -eu
python -c 'from app.main import apply_schema; apply_schema()'
make seed
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
