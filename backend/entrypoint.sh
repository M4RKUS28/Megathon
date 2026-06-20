#!/bin/sh
# Apply database migrations, then hand off to the container's command
# (uvicorn). Runs once per container start, before any workers fork.
set -e

echo "[entrypoint] Applying database migrations..."
uv run alembic upgrade head

echo "[entrypoint] Starting: $*"
exec "$@"
