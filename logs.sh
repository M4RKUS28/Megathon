#!/usr/bin/env bash
# Tail the stack's logs. Follows all services by default; pass service names to
# narrow it down, e.g. ./logs.sh backend  or  ./logs.sh backend keycloak
# Works on Linux/macOS and Windows git-bash.
set -Eeuo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose --project-directory . \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.override.yml)

if [ $# -eq 1 ] && { [ "$1" = "-h" ] || [ "$1" = "--help" ]; }; then
  echo "Usage: ./logs.sh [service...]"
  echo "  Follows logs for all services, or only the given ones."
  echo "  Example: ./logs.sh backend keycloak"
  exit 0
fi

# -f follows, --tail=100 starts with recent context instead of full history.
"${COMPOSE[@]}" logs -f --tail=100 "$@"
