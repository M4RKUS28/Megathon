#!/usr/bin/env bash
# One-command local dev shutdown. Stops the stack started by ./run.sh.
# By default containers and networks are removed but named volumes (DB, MinIO,
# Keycloak data) are kept. Pass -v / --volumes to wipe data for a clean slate.
# Works on Linux/macOS and Windows git-bash.
set -Eeuo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose --project-directory . \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.override.yml)

# Parse args: -v/--volumes also removes named volumes (destroys local data).
REMOVE_VOLUMES=0
for arg in "$@"; do
  case "$arg" in
    -v|--volumes) REMOVE_VOLUMES=1 ;;
    -h|--help)
      echo "Usage: ./stop.sh [-v|--volumes]"
      echo "  -v, --volumes   Also remove named volumes (wipes DB/MinIO/Keycloak data)."
      exit 0
      ;;
    *) echo "[stop] Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# Bring the stack down. --remove-orphans cleans up containers no longer in the
# compose files; -v additionally deletes the named volumes.
if [ "$REMOVE_VOLUMES" -eq 1 ]; then
  echo "[stop] Stopping stack and removing volumes (local data will be wiped)..."
  "${COMPOSE[@]}" down --remove-orphans -v
else
  echo "[stop] Stopping stack (volumes/data preserved)..."
  "${COMPOSE[@]}" down --remove-orphans
fi

echo "[stop] Done."
