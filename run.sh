#!/usr/bin/env bash
# One-command local dev launcher. Goal: a clean `git clone` + `./run.sh` boots
# the whole stack with no manual steps. Works on Linux/macOS and Windows git-bash.
set -Eeuo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose --project-directory . \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.override.yml)

# 1) .env is gitignored, so a fresh clone has none. Seed it from the example.
#    Offline fallbacks work without provider keys; add keys to .env to enable
#    Gemini / Cala / PixVerse.
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[run] Created .env from .env.example."
fi

# 2) Build + start everything. The backend entrypoint applies DB migrations
#    (alembic upgrade head) automatically on start.
"${COMPOSE[@]}" up -d --build

# 3) Wait for the API, then seed the demo company/users (idempotent, non-fatal).
echo "[run] Waiting for backend API..."
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null http://localhost:8000/docs 2>/dev/null; then break; fi
  sleep 2
done
echo "[run] Seeding demo data..."
"${COMPOSE[@]}" exec -T backend uv run python -m src.db.seed \
  || echo "[run] Seed step skipped (run it manually if you need demo data)."

"${COMPOSE[@]}" ps
cat <<'EOF'

[run] Ready:
  App (nginx):       http://localhost
  Frontend (Vite):   http://localhost:5173
  Backend API docs:  http://localhost:8000/docs
  Keycloak:          http://localhost:8080
  MinIO console:     http://localhost:9001

  Demo logins (Keycloak realm "app"):
    creator@acme.test  / creator2026
    admin@acme.test    / admin2026
    employee@acme.test / employee2026
EOF
