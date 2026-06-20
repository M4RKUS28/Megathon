from fastapi import APIRouter

from src.api.v1.endpoints.branding import router as branding_router
from src.api.v1.endpoints.files import router as files_router
from src.api.v1.endpoints.me import router as me_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(files_router)
api_router.include_router(me_router)
api_router.include_router(branding_router)
