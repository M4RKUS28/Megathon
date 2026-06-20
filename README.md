# Fullstack Template

React + FastAPI + PostgreSQL + Keycloak + MinIO, served via Nginx — single Docker Compose setup.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui |
| Routing | React Router v7 |
| Server state | TanStack Query |
| Auth (client) | keycloak-js (PKCE) |
| Backend | FastAPI, Python 3.12, uv |
| Auth (server) | python-keycloak, JWT via JWKS |
| ORM | SQLAlchemy 2.0 async + mapped_column |
| Migrations | Alembic |
| Config | pydantic-settings |
| Database | PostgreSQL 16 |
| Object storage | MinIO |
| Proxy | Nginx |
| Auth server | Keycloak 24 |

---

## Project structure

```
.
├── docker-compose.yml            # production
├── docker-compose.override.yml   # dev (hot reload, exposed ports)
├── .env.example
├── nginx/
│   ├── nginx.conf
│   └── conf.d/
│       ├── default.conf          # prod routing
│       └── dev.conf              # dev routing
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── env.py
│   └── src/
│       ├── main.py
│       ├── config/
│       │   └── settings.py       # all env vars via pydantic-settings
│       ├── core/
│       │   ├── auth.py           # JWT validation, current_user dep, require_role()
│       │   └── exceptions.py     # AppError hierarchy + FastAPI handler
│       ├── db/
│       │   ├── database.py       # async engine, session factory, Base, get_db()
│       │   ├── minio.py          # MinIO client, presigned URLs, object helpers
│       │   ├── models/           # SQLAlchemy ORM models
│       │   └── crud/             # async CRUD functions per model
│       ├── services/             # business logic layer
│       └── api/
│           └── v1/
│               ├── router.py
│               ├── schemas/      # Pydantic request/response models
│               └── endpoints/    # route handlers
└── frontend/
    ├── Dockerfile
    ├── nginx.conf                # SPA fallback for prod container
    ├── public/
    │   └── silent-check-sso.html # Keycloak silent SSO
    └── src/
        ├── main.tsx
        ├── router.tsx            # route definitions, protected routes
        ├── index.css             # Tailwind + CSS variables (light/dark)
        ├── lib/
        │   ├── auth.ts           # Keycloak init, login/logout, token helpers
        │   ├── api.ts            # axios instance with auto-token interceptor
        │   ├── query-client.ts   # TanStack Query client
        │   └── utils.ts          # cn(), shared helpers
        ├── hooks/                # TanStack Query hooks per domain
        ├── components/
        │   ├── ui/               # shadcn/ui components (add via CLI)
        │   ├── Layout.tsx        # nav shell with Outlet
        │   └── ProtectedRoute.tsx# auth + role guard
        └── pages/                # one file per route
```

---

## Services & ports

| Service | Internal | Exposed (dev) |
|---|---|---|
| Nginx | 80 | 80 |
| Frontend (Vite) | 5173 | 5173 |
| Backend (FastAPI) | 8000 | 8000 |
| Keycloak | 8080 | 8080 |
| PostgreSQL | 5432 | 5432 |
| MinIO API | 9000 | 9000 |
| MinIO Console | 9001 | 9001 |

In production all traffic goes through Nginx on port 80/443. Keycloak runs on a separate subdomain (`auth.yourdomain.com`).

---

## Nginx routing (prod)

```
yourdomain.com/api/*   →  backend:8000
yourdomain.com/        →  frontend:80  (SPA fallback)
auth.yourdomain.com    →  keycloak:8080
```

---

## Getting started

```bash
cp .env.example .env
# edit .env — set DOMAIN, AUTH_DOMAIN, passwords, secrets

# Dev (hot reload)
docker compose up

# Production
docker compose -f docker-compose.yml up -d
```

**Initial setup (first run):**

1. Open Keycloak at `http://localhost:8080`, create realm `app` and client `app-frontend` (public client, PKCE enabled, redirect URI `http://localhost/*`).
2. Run database migrations:
   ```bash
   docker compose exec backend uv run alembic upgrade head
   ```

---

## Adding new API routes

1. Add a SQLAlchemy model in `backend/src/db/models/`
2. Register it in `backend/src/db/models/__init__.py`
3. Add CRUD functions in `backend/src/db/crud/`
4. Add business logic in `backend/src/services/`
5. Add Pydantic schemas in `backend/src/api/v1/schemas/`
6. Add endpoint file in `backend/src/api/v1/endpoints/` and register it in `api/v1/router.py`
7. Create and apply a migration: `uv run alembic revision --autogenerate -m "add_thing"` then `uv run alembic upgrade head`

## Adding shadcn/ui components

```bash
cd frontend
npx shadcn@latest add button
npx shadcn@latest add input dialog
```

Components are copied into `src/components/ui/` and owned by your project.
