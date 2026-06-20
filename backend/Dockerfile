FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN pip install uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Course template build (Vite) ─────────────────────────────────────────────
# The generated-course player is a Vite app that loads concept.json at runtime.
# It is built once here and bundled into the image; the worker publishes a copy
# (plus each course's concept.json) to MinIO per course.
FROM node:20-slim AS course-build
WORKDIR /tpl
COPY courses-template/package*.json ./
RUN npm ci
COPY courses-template/ ./
RUN npm run build

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development

RUN uv sync --frozen
COPY backend/ .
COPY --from=course-build /tpl/dist /app/course_template_dist

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS production

COPY backend/ .
COPY --from=course-build /tpl/dist /app/course_template_dist

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
