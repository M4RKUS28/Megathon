import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.config.settings import settings
from src.core.exceptions import AppError, app_error_handler
from src.db.minio import ensure_bucket_exists
from src.db.seed import seed_demo_data

logging.basicConfig(level=settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic migrations applied on container start
    # (see entrypoint.sh -> `alembic upgrade head`).
    ensure_bucket_exists()
    ensure_bucket_exists(settings.courses_bucket)
    try:
        await seed_demo_data()
    except Exception:  # noqa: BLE001 — seeding is best-effort, never block boot
        logger.exception("Demo data seeding failed")
    yield


app = FastAPI(
    title="App API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
