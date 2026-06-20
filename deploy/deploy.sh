#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  echo "Create it from $PROJECT_ROOT/.env.example.prod and fill in the production values." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not available on PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available." >&2
  exit 1
fi

compose=(docker compose --env-file "$ENV_FILE" --project-directory "$PROJECT_ROOT" -f "$COMPOSE_FILE")

"${compose[@]}" pull
"${compose[@]}" up -d --remove-orphans
"${compose[@]}" ps
