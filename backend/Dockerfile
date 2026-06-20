FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Per-course app template (Vite) ───────────────────────────────────────────
# Each course is compiled into its OWN Vite/React/TS app from this template; the
# builder copies these sources, bakes in course.json/asset_map.json and runs
# `npm run build` to produce that course's dist/, which is published to MinIO.
FROM node:22-slim AS course-app-template
WORKDIR /course_app_template
COPY course-app-template/package*.json ./
RUN npm ci
COPY course-app-template/ ./

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development

RUN uv sync --frozen
COPY backend/ .
COPY --from=course-app-template /course_app_template /app/course_app_template

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS production

COPY backend/ .
COPY --from=course-app-template /course_app_template /app/course_app_template

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
