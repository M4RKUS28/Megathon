docker compose --project-directory . \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.override.yml \
  up -d --build