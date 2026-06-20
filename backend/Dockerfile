FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development

RUN uv sync --frozen
COPY . .

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS production

COPY . .

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
