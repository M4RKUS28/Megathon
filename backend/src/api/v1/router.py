from fastapi import APIRouter

from src.api.v1.endpoints.files import router as files_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(files_router)
