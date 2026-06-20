from fastapi import APIRouter

from src.api.v1.endpoints.branding import router as branding_router
from src.api.v1.endpoints.companies import router as companies_router
from src.api.v1.endpoints.courses import router as courses_router
from src.api.v1.endpoints.files import router as files_router
from src.api.v1.endpoints.me import router as me_router
from src.api.v1.endpoints.people import router as people_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(files_router)
api_router.include_router(me_router)
api_router.include_router(branding_router)
api_router.include_router(people_router)
api_router.include_router(companies_router)
api_router.include_router(courses_router)
