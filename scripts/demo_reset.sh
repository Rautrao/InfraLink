#!/usr/bin/env sh
set -eu

api_base=${DEMO_API_BASE:-http://localhost:8000/api/v1}
curl --fail --silent --show-error --max-time 25 -X POST "${api_base%/}/dev/reset-seed"
printf '\nDemo data reset completed.\n'
