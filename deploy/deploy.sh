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
  if command -v ip >/dev/null 2>&1; then
    ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
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

normalize_public_url_values() {
  local public_url
  local minio_public_url
  local cors_origins
  local changed="false"

  public_url="$(env_value PLATFORM_PUBLIC_URL)"
  if [[ -z "$public_url" || "$public_url" == "http://203.0.113.10" || "$public_url" == "https://203.0.113.10" ]]; then
    public_url="$(detect_public_url)"
    set_env_value PLATFORM_PUBLIC_URL "$public_url"
    changed="true"
  fi
  public_url="${public_url%/}"

  minio_public_url="$(env_value MINIO_PUBLIC_URL)"
  if [[ -z "$minio_public_url" || "$minio_public_url" == "http://203.0.113.10/storage" || "$minio_public_url" == "https://203.0.113.10/storage" ]]; then
    set_env_value MINIO_PUBLIC_URL "$public_url/storage"
    changed="true"
  fi

  cors_origins="$(env_value CORS_ORIGINS)"
  if [[ -z "$cors_origins" || "$cors_origins" == '["http://203.0.113.10"]' || "$cors_origins" == '["https://203.0.113.10"]' ]]; then
    set_env_value CORS_ORIGINS "[\"$public_url\"]"
    changed="true"
  fi

  if [[ "$changed" == "true" ]]; then
    echo "Updated placeholder public URLs in $ENV_FILE to $public_url."
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

find_traefik_container_ids() {
  local configured
  configured="$(env_value TRAEFIK_CONTAINER)"
  if [[ -n "$configured" ]]; then
    docker ps --filter "id=$configured" --format '{{.ID}}'
    docker ps --filter "name=$configured" --format '{{.ID}}'
    return
  fi
  docker ps --format '{{.ID}}\t{{.Image}}\t{{.Names}}' | grep -i "traefik" | awk '{ print $1 }' || true
}

container_is_on_network() {
  local container_id="$1"
  local network="$2"
  local attached
  attached="$(
    docker inspect --format "{{ if index .NetworkSettings.Networks \"$network\" }}true{{ end }}" "$container_id" 2>/dev/null || true
  )"
  [[ "$attached" == "true" ]]
}

connect_traefik_to_network() {
  local network="$1"
  local found="false"
  local seen=" "
  local container_id
  while IFS= read -r container_id; do
    [[ -z "$container_id" ]] && continue
    [[ "$seen" == *" $container_id "* ]] && continue
    seen="${seen}${container_id} "
    found="true"
    if ! container_is_on_network "$container_id" "$network"; then
      docker network connect "$network" "$container_id"
      echo "Connected Traefik container $container_id to Docker network: $network"
    fi
  done < <(find_traefik_container_ids)

  if [[ "$found" != "true" ]]; then
    echo "No running Traefik container detected. Ensure Traefik is running and attached to Docker network '$network', or set TRAEFIK_CONTAINER in $ENV_FILE." >&2
  fi
}

sync_keycloak_client_redirects() {
  local public_url
  local realm
  local client_id
  local admin_user
  local admin_password
  local client_uuid
  local attempt
  local redirect_uris
  local logout_redirect_uris

  public_url="$(env_value PLATFORM_PUBLIC_URL)"
  public_url="${public_url%/}"
  realm="$(env_value KEYCLOAK_REALM)"
  realm="${realm:-app}"
  client_id="$(env_value VITE_KEYCLOAK_CLIENT_ID)"
  client_id="${client_id:-$(env_value KEYCLOAK_CLIENT_ID)}"
  client_id="${client_id:-app-frontend}"
  admin_user="$(env_value KEYCLOAK_ADMIN)"
  admin_password="$(env_value KEYCLOAK_ADMIN_PASSWORD)"

  if [[ -z "$public_url" || -z "$admin_user" || -z "$admin_password" ]]; then
    echo "Skipping Keycloak redirect URI sync because PLATFORM_PUBLIC_URL, KEYCLOAK_ADMIN or KEYCLOAK_ADMIN_PASSWORD is empty." >&2
    return
  fi

  for attempt in {1..36}; do
    if "${compose[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user "$admin_user" --password "$admin_password" >/dev/null 2>&1; then
      break
    fi
    if [[ "$attempt" == "36" ]]; then
      echo "Skipping Keycloak redirect URI sync because Keycloak admin login did not become ready." >&2
      return
    fi
    sleep 5
  done

  client_uuid="$(
    "${compose[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh get clients -r "$realm" -q "clientId=$client_id" --fields id --format csv 2>/dev/null \
      | awk -F, '{ gsub(/\r|"/, "", $1); if ($1 != "" && $1 != "id") { print $1; exit } }'
  )"

  if [[ -z "$client_uuid" ]]; then
    echo "Skipping Keycloak redirect URI sync because client '$client_id' was not found in realm '$realm'." >&2
    return
  fi

  redirect_uris="[\"http://localhost/*\",\"http://localhost:5173/*\",\"$public_url/*\"]"
  logout_redirect_uris="http://localhost/*##http://localhost:5173/*##$public_url/*"

  "${compose[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh update "clients/$client_uuid" -r "$realm" \
    -s "redirectUris=$redirect_uris" \
    -s 'webOrigins=["+"]' \
    -s 'attributes."pkce.code.challenge.method"=S256' \
    -s "attributes.\"post.logout.redirect.uris\"=$logout_redirect_uris" >/dev/null

  echo "Updated Keycloak client '$client_id' redirect URIs for $public_url."
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
normalize_public_url_values
normalize_image_values

TRAEFIK_NETWORK="$(env_value TRAEFIK_NETWORK)"
TRAEFIK_NETWORK="${TRAEFIK_NETWORK:-traefik}"

if ! docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1; then
  docker network create "$TRAEFIK_NETWORK" >/dev/null
  echo "Created Docker network: $TRAEFIK_NETWORK"
fi

connect_traefik_to_network "$TRAEFIK_NETWORK"

export PROJECT_ROOT

compose=(docker compose --env-file "$ENV_FILE" --project-directory "$PROJECT_ROOT" -f "$COMPOSE_FILE")

"${compose[@]}" config >/dev/null
"${compose[@]}" up -d --build --remove-orphans
sync_keycloak_client_redirects
"${compose[@]}" ps
