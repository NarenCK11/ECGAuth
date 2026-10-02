#!/bin/sh
set -e

# Apply database migrations, optionally load the demonstration data, then serve.
alembic upgrade head

if [ "${SEED_DEMO:-false}" = "true" ]; then
  python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
