from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(404, f"{resource} not found")


class ForbiddenError(AppError):
    def __init__(self) -> None:
        super().__init__(403, "Forbidden")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
