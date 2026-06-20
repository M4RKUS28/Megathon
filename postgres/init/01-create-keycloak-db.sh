#!/bin/sh
# Runs only on first initialization of an empty Postgres data directory.
# Creates a dedicated database for Keycloak so it doesn't share the
# application's database (KEYCLOAK_DB is passed via the postgres service env).
set -e

db="${KEYCLOAK_DB:-keycloak}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"$db\" OWNER \"$POSTGRES_USER\";"

echo "[init] Created database '$db' for Keycloak"
