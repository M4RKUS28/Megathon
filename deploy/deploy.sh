#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example.prod"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

env_value() {
  local key="$1"
  local line
  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)"
  line="${line#*=}"
  line="${line%$'\r'}"
  line="${line%\"}"
  line="${line#\"}"
  line="${line%\'}"
  line="${line#\'}"
  printf '%s' "$line"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" { print key "=" value; found = 1; next }
    { print }
    END { if (found == 0) print key "=" value }
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
}

random_hex() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

detect_public_url() {
  local ip=""
  if command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v ip >/dev/null 2>&1; then
    ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v ipconfig >/dev/null 2>&1; then
    ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  fi
  if [[ -z "$ip" ]]; then
    ip="127.0.0.1"
  fi
  printf 'http://%s' "$ip"
}

prepare_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_EXAMPLE" ]]; then
      echo "Missing env file: $ENV_FILE" >&2
      echo "Missing example env file: $ENV_EXAMPLE" >&2
      exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    local public_url
    public_url="$(detect_public_url)"
    set_env_value PLATFORM_PUBLIC_URL "$public_url"
    set_env_value MINIO_PUBLIC_URL "$public_url/storage"
    set_env_value CORS_ORIGINS "[\"$public_url\"]"
    set_env_value POSTGRES_PASSWORD "$(random_hex)"
    set_env_value MINIO_ROOT_PASSWORD "$(random_hex)"
    set_env_value KEYCLOAK_ADMIN_PASSWORD "$(random_hex)"
    set_env_value KEYCLOAK_CLIENT_SECRET "$(random_hex)"
    set_env_value SECRET_KEY "$(random_hex)"
    echo "Created $ENV_FILE from .env.example.prod"
    echo "Review $ENV_FILE before exposing this server publicly."
  fi
}

normalize_image_values() {
  local changed="false"
  if [[ "$(env_value BACKEND_IMAGE)" == "docker.io/your-dockerhub-user/megathon-backend" ]]; then
    set_env_value BACKEND_IMAGE "coursive-backend"
    changed="true"
  fi
  if [[ "$(env_value FRONTEND_IMAGE)" == "docker.io/your-dockerhub-user/megathon-frontend" ]]; then
    set_env_value FRONTEND_IMAGE "coursive-frontend"
    changed="true"
  fi
  if [[ "$changed" == "true" && "$(env_value IMAGE_TAG)" == "latest" ]]; then
    set_env_value IMAGE_TAG "local"
  fi
  if [[ "$changed" == "true" ]]; then
    echo "Updated placeholder image names in $ENV_FILE to local build image names."
  fi
}

require_command docker
require_command grep
require_command awk
require_command od
require_command tr
require_command mktemp

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available." >&2
  exit 1
fi

prepare_env_file
normalize_image_values

TRAEFIK_NETWORK="$(env_value TRAEFIK_NETWORK)"
TRAEFIK_NETWORK="${TRAEFIK_NETWORK:-traefik}"

if ! docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1; then
  docker network create "$TRAEFIK_NETWORK" >/dev/null
  echo "Created Docker network: $TRAEFIK_NETWORK"
fi

export PROJECT_ROOT

compose=(docker compose --env-file "$ENV_FILE" --project-directory "$PROJECT_ROOT" -f "$COMPOSE_FILE")

"${compose[@]}" config >/dev/null
"${compose[@]}" up -d --build --remove-orphans
"${compose[@]}" ps
