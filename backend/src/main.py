import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.core.exceptions import AppError, app_error_handler
from src.api.v1.router import api_router
from src.db.minio import ensure_bucket_exists

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="App API", version="1.0.0", docs_url="/docs", redoc_url="/redoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.include_router(api_router)


@app.on_event("startup")
async def startup() -> None:
    # Schema is managed by Alembic migrations, applied on container start
    # (see entrypoint.sh -> `alembic upgrade head`).
    ensure_bucket_exists()


@app.get("/health")
async def health():
    return {"status": "ok"}
